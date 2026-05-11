import { randomUUID } from "node:crypto";
import { createMcpExpressApp } from "@modelcontextprotocol/express";
import { NodeStreamableHTTPServerTransport } from "@modelcontextprotocol/node";
import { McpServer } from "@modelcontextprotocol/server";
import express from "express";
import * as z from "zod/v4";
import {
  BusinessError,
  errorPayload,
  getAssetDetails,
  getUserDetails,
  getUserOrders,
  submitWorkOrder
} from "./business.js";

const HOST = process.env.BOU_BUSINESS_HOST || "127.0.0.1";
const PORT = Number(process.env.BOU_BUSINESS_PORT || 8011);
const AUTH_TOKEN = process.env.BOU_BUSINESS_TOKEN || "";

const assetTypeSchema = z.enum(["vip_weekly", "vip_monthly", "coin"]);
const datetimeRangeSchema = z
  .object({
    start: z.string(),
    end: z.string()
  })
  .optional();

function assertAuth(req, res, next) {
  if (!AUTH_TOKEN) {
    next();
    return;
  }

  const auth = req.headers.authorization || "";
  if (auth !== `Bearer ${AUTH_TOKEN}`) {
    res.status(401).json(errorPayload(new BusinessError(401, "UNAUTHORIZED", "Invalid business auth token")));
    return;
  }
  next();
}

function toolResult(payload) {
  return {
    content: [{ type: "text", text: JSON.stringify(payload) }],
    structuredContent: payload,
    isError: payload?.success === false
  };
}

async function runBusinessTool(fn) {
  try {
    return toolResult(await fn());
  } catch (error) {
    return toolResult(errorPayload(error));
  }
}

function createBusinessMcpServer() {
  const server = new McpServer({
    name: "bou-business",
    version: "0.1.0"
  });

  server.registerTool(
    "get_user_details",
    {
      description: "查询用户资产概览，包括月卡VIP状态、周卡VIP状态、回声贝余额、星能余额等",
      inputSchema: z.object({
        user_id: z.string().describe("BOU user id")
      })
    },
    async ({ user_id }) => runBusinessTool(() => getUserDetails(user_id))
  );

  server.registerTool(
    "get_user_recent_orders",
    {
      description: "获取用户订单列表，可能是周卡VIP、月卡VIP、回声贝购买订单",
      inputSchema: z.object({
        user_id: z.string().describe("BOU user id"),
        datetime_range: datetimeRangeSchema,
        asset_type: assetTypeSchema.optional(),
        limit: z.number().int().min(1).max(20).default(5)
      })
    },
    async ({ user_id, datetime_range, asset_type, limit }) =>
      runBusinessTool(() =>
        getUserOrders(user_id, {
          limit,
          assetType: asset_type,
          datetimeRange: datetime_range
        })
      )
  );

  server.registerTool(
    "get_asset_details",
    {
      description: "查询用户某类型资产的明细流水",
      inputSchema: z.object({
        user_id: z.string().describe("BOU user id"),
        datetime_range: datetimeRangeSchema,
        asset_type: assetTypeSchema
      })
    },
    async ({ user_id, datetime_range, asset_type }) =>
      runBusinessTool(() =>
        getAssetDetails(user_id, asset_type, {
          datetimeRange: datetime_range
        })
      )
  );

  server.registerTool(
    "submit_work_order",
    {
      description: "提交工单",
      inputSchema: z.object({
        user_id: z.string(),
        issue_type: z.string(),
        description: z.string(),
        order_id: z.string().optional(),
        priority: z.enum(["low", "normal", "high"]).default("normal")
      })
    },
    async (args) => runBusinessTool(() => submitWorkOrder(args))
  );

  return server;
}

function sendRest(res, statusCode, payload) {
  res.status(statusCode).json(payload);
}

const app = createMcpExpressApp();
app.use(express.json());
app.use(assertAuth);

app.get("/health", (_req, res) => {
  sendRest(res, 200, { status: "ok", service: "bou-business" });
});

app.get("/api/users/:user_id/orders", (req, res) => {
  sendRest(res, 200, getUserOrders(req.params.user_id, {
    limit: req.query.limit || 5,
    assetType: req.query.asset_type || undefined,
    datetimeRange: {
      start: req.query.start || null,
      end: req.query.end || null
    }
  }));
});

app.get("/api/users/:user_id/assets", (req, res) => {
  sendRest(res, 200, getUserDetails(req.params.user_id));
});

app.get("/api/users/:user_id/assets/:asset_type/details", (req, res) => {
  sendRest(res, 200, getAssetDetails(req.params.user_id, req.params.asset_type, {
    datetimeRange: {
      start: req.query.start || null,
      end: req.query.end || null
    }
  }));
});

app.post("/api/work-orders", (req, res) => {
  sendRest(res, 201, submitWorkOrder(req.body || {}));
});

app.post("/mcp", async (req, res) => {
  const server = createBusinessMcpServer();
  const transport = new NodeStreamableHTTPServerTransport({
    sessionIdGenerator: undefined,
    enableJsonResponse: true
  });

  res.on("close", async () => {
    await transport.close().catch(() => undefined);
    await server.close().catch(() => undefined);
  });

  try {
    await server.connect(transport);
    await transport.handleRequest(req, res, req.body);
  } catch (error) {
    console.error("Error handling MCP request:", error);
    if (!res.headersSent) {
      res.status(500).json({
        jsonrpc: "2.0",
        error: { code: -32603, message: "Internal server error" },
        id: null
      });
    }
  }
});

app.get("/mcp", (_req, res) => {
  res.status(405).set("Allow", "POST").send("Method Not Allowed");
});

app.delete("/mcp", (_req, res) => {
  res.status(405).set("Allow", "POST").send("Method Not Allowed");
});

app.use((error, _req, res, _next) => {
  const statusCode = error instanceof BusinessError ? error.statusCode : 500;
  sendRest(res, statusCode, errorPayload(error));
});

app.listen(PORT, HOST, () => {
  console.log(`bou-business listening at http://${HOST}:${PORT} (${randomUUID().slice(0, 8)})`);
});
