import crypto from "node:crypto";
import { users, workOrders } from "./data.js";

const USER_ID_PATTERN = /^[a-zA-Z0-9_-]{3,64}$/;
const ASSET_TYPES = new Set(["vip_weekly", "vip_monthly", "coin"]);

const WORK_ORDER_ISSUE_TYPES = new Set([
  "月卡未到账",
  "周卡未到账",
  "回声贝未到账",
  "虚拟资产未到账",
  "体力异常",
  "订单异常",
  "聊天质量反馈"
]);

export class BusinessError extends Error {
  constructor(statusCode, code, message, details = {}) {
    super(message);
    this.name = "BusinessError";
    this.statusCode = statusCode;
    this.code = code;
    this.details = details;
  }
}

function nowIso() {
  return new Date().toISOString();
}

function hash(input) {
  return crypto.createHash("sha256").update(input).digest("hex");
}

function validateUserId(userId) {
  if (!userId || !USER_ID_PATTERN.test(userId)) {
    throw new BusinessError(400, "INVALID_ARGUMENT", "user_id must be 3-64 chars: letters, numbers, _ or -", {
      field: "user_id"
    });
  }
}

function getUser(userId) {
  validateUserId(userId);
  const user = users[userId];
  if (!user) {
    throw new BusinessError(404, "USER_NOT_FOUND", "User not found", { user_id: userId });
  }
  return user;
}

function success(data) {
  return { success: true, ...data };
}

function parseTime(value) {
  if (!value) return null;
  const time = Date.parse(value);
  if (Number.isNaN(time)) {
    throw new BusinessError(400, "INVALID_ARGUMENT", "datetime_range must contain valid date-time strings", {
      field: "datetime_range"
    });
  }
  return time;
}

function inDatetimeRange(value, datetimeRange) {
  if (!datetimeRange) return true;
  const itemTime = parseTime(value);
  const startTime = parseTime(datetimeRange.start);
  const endTime = parseTime(datetimeRange.end);

  if (startTime && itemTime < startTime) return false;
  if (endTime && itemTime > endTime) return false;
  return true;
}

function validateAssetType(assetType) {
  if (!ASSET_TYPES.has(assetType)) {
    throw new BusinessError(400, "INVALID_ARGUMENT", "Unsupported asset_type", {
      field: "asset_type",
      allowed: Array.from(ASSET_TYPES)
    });
  }
}

export function errorPayload(error) {
  if (error instanceof BusinessError) {
    return {
      success: false,
      error: {
        code: error.code,
        message: error.message,
        details: error.details
      }
    };
  }

  return {
    success: false,
    error: {
      code: "INTERNAL_ERROR",
      message: error?.message || "Internal error",
      details: {}
    }
  };
}

export function getUserDetails(userId) {
  const user = getUser(userId);
  return success({
    user_id: userId,
    profile: user.profile,
    assets: Object.values(user.assets),
    diagnosis: buildAssetDiagnosis(user)
  });
}

export function getUserOrders(userId, options = {}) {
  const user = getUser(userId);
  const safeLimit = Math.min(Math.max(Number(options.limit) || 5, 1), 20);
  const assetType = options.assetType;

  if (assetType) validateAssetType(assetType);

  const orders = user.orders
    .filter((order) => !assetType || order.product_type === assetType)
    .filter((order) => inDatetimeRange(order.paid_at, options.datetimeRange))
    .slice(0, safeLimit);

  return success({
    user_id: userId,
    orders
  });
}

export function getAssetDetails(userId, assetType, options = {}) {
  validateAssetType(assetType);
  const user = getUser(userId);
  const asset = user.assets[assetType];
  if (!asset) {
    throw new BusinessError(404, "ASSET_NOT_FOUND", "Asset not found", { asset_type: assetType });
  }

  const details = (user.asset_details[assetType] || []).filter((item) =>
    inDatetimeRange(item.created_at, options.datetimeRange)
  );

  return success({
    user_id: userId,
    asset,
    details
  });
}

export function submitWorkOrder(payload) {
  const userId = payload.user_id;
  const issueType = payload.issue_type;
  const description = String(payload.description || "").trim();
  const orderId = String(payload.order_id || "").trim();
  const priority = payload.priority || "normal";

  getUser(userId);

  if (!WORK_ORDER_ISSUE_TYPES.has(issueType)) {
    throw new BusinessError(400, "INVALID_ARGUMENT", "Unsupported issue_type", {
      field: "issue_type",
      allowed: Array.from(WORK_ORDER_ISSUE_TYPES)
    });
  }
  if (description.length < 6) {
    throw new BusinessError(400, "INVALID_ARGUMENT", "description must be at least 6 chars", {
      field: "description"
    });
  }
  if (!["low", "normal", "high"].includes(priority)) {
    throw new BusinessError(400, "INVALID_ARGUMENT", "priority must be low, normal or high", {
      field: "priority"
    });
  }

  const key = hash(`${userId}|${issueType}|${orderId}|${description.slice(0, 120)}`);
  const existing = workOrders.get(key);
  if (existing) {
    return success({ work_order: { ...existing, idempotent: true } });
  }

  const ticketId = `WO_${String(workOrders.size + 1).padStart(6, "0")}`;
  const workOrder = {
    ticket_id: ticketId,
    user_id: userId,
    issue_type: issueType,
    description,
    order_id: orderId || null,
    priority,
    status: "submitted",
    created_at: nowIso(),
    idempotent: false
  };
  workOrders.set(key, workOrder);
  return success({ work_order: workOrder });
}

export function buildAssetDiagnosis(user) {
  const timeoutOrders = user.orders.filter(
    (order) => order.payment_status === "paid" && order.delivery_status === "callback_timeout"
  );
  const abnormalAssets = Object.values(user.assets).filter((asset) =>
    ["abnormal", "not_delivered"].includes(asset.status)
  );

  if (timeoutOrders.length || abnormalAssets.length) {
    return {
      status: "abnormal",
      reason: "存在支付成功但权益未到账或资产异常记录",
      related_order_ids: timeoutOrders.map((order) => order.order_id),
      related_asset_ids: abnormalAssets.map((asset) => asset.asset_id)
    };
  }

  return {
    status: "normal",
    reason: "未发现明显资产异常",
    related_order_ids: [],
    related_asset_ids: []
  };
}
