export const users = {
  helloworld666: {
    profile: {
      user_id: "helloworld666",
      nickname: "BOU Test User",
      level: 18
    },
    orders: [
      {
        order_id: "ORD_20260501_1001",
        product_type: "vip_monthly",
        product: "BOU月卡（30天体力+150）",
        amount: 30,
        payment_status: "paid",
        delivery_status: "callback_timeout",
        paid_at: "2026-05-01T14:32:07+08:00"
      }
    ],
    assets: {
      vip_monthly: {
        asset_id: "asset_vip_monthly",
        name: "月卡会员",
        type: "vip_monthly",
        balance: 0,
        status: "not_delivered",
        expire_at: null
      },
      stamina: {
        asset_id: "asset_stamina",
        name: "体力",
        type: "stamina",
        balance: 0,
        status: "abnormal",
        expire_at: null
      },
      coin: {
        asset_id: "asset_coin",
        name: "回声贝",
        type: "coin",
        balance: 260,
        status: "normal",
        expire_at: null
      },
      star_energy: {
        asset_id: "asset_star_energy",
        name: "星能",
        type: "star_energy",
        balance: 42,
        status: "normal",
        expire_at: null
      }
    },
    asset_details: {
      vip_monthly: [],
      stamina: [],
      coin: [
        {
          detail_id: "ASTD_666_001",
          change_type: "consume",
          amount: -60,
          scene: "角色聊天",
          related_order_id: null,
          created_at: "2026-05-02T20:15:12+08:00"
        },
        {
          detail_id: "ASTD_666_002",
          change_type: "consume",
          amount: -30,
          scene: "语音互动",
          related_order_id: null,
          created_at: "2026-05-05T21:08:34+08:00"
        },
        {
          detail_id: "ASTD_666_003",
          change_type: "grant",
          amount: 100,
          scene: "活动奖励",
          related_order_id: null,
          created_at: "2026-05-06T12:00:00+08:00"
        }
      ]
    }
  },
  user_1001: {
    profile: {
      user_id: "user_1001",
      nickname: "Test Monthly User",
      level: 12
    },
    orders: [
      {
        order_id: "ORD_20260423_1001",
        product_type: "vip_monthly",
        product: "BOU月卡（30天体力+150）",
        amount: 30,
        payment_status: "paid",
        delivery_status: "callback_timeout",
        paid_at: "2026-04-23T11:05:23+08:00"
      }
    ],
    assets: {
      vip_monthly: {
        asset_id: "asset_vip_monthly",
        name: "月卡会员",
        type: "vip_monthly",
        balance: 0,
        status: "not_delivered",
        expire_at: null
      },
      stamina: {
        asset_id: "asset_stamina",
        name: "体力",
        type: "stamina",
        balance: 0,
        status: "abnormal",
        expire_at: null
      }
    },
    asset_details: {
      vip_monthly: [],
      stamina: []
    }
  },
  user_1002: {
    profile: {
      user_id: "user_1002",
      nickname: "Test Weekly User",
      level: 9
    },
    orders: [
      {
        order_id: "ORD_20260424_1002",
        product_type: "vip_weekly",
        product: "BOU周卡",
        amount: 12,
        payment_status: "paid",
        delivery_status: "delivered",
        paid_at: "2026-04-24T09:20:00+08:00"
      }
    ],
    assets: {
      vip_weekly: {
        asset_id: "asset_vip_weekly",
        name: "周卡会员",
        type: "vip_weekly",
        balance: 1,
        status: "active",
        expire_at: "2026-05-10T23:59:59+08:00"
      },
      stamina: {
        asset_id: "asset_stamina",
        name: "体力",
        type: "stamina",
        balance: 150,
        status: "normal",
        expire_at: null
      }
    },
    asset_details: {
      vip_weekly: [
        {
          detail_id: "ASTD_1002_001",
          change_type: "grant",
          amount: 1,
          related_order_id: "ORD_20260424_1002",
          created_at: "2026-04-24T09:20:05+08:00"
        }
      ],
      stamina: [
        {
          detail_id: "ASTD_1002_002",
          change_type: "grant",
          amount: 150,
          related_order_id: "ORD_20260424_1002",
          created_at: "2026-04-24T09:20:05+08:00"
        }
      ]
    }
  }
};

export const workOrders = new Map();
