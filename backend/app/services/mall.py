"""电商联盟客户端（数据源用途）。

模式由 settings.mall_mode 显式控制（不做静默降级）：
- mock：开发联调，返回嵌入真实品牌的演示商品（品牌从 seed.csv 动态取样）
- taobao：真实调用 taobao.tbk.dg.material.optional，缺 AppKey 在初始化时立即报错

注意：本应用不使用返佣（不运营推广位），仅以联盟 API 作为商品库/实时价格/跳转链接来源。
"""

import hashlib
import random
import time
from pathlib import Path

import httpx

from ..config import settings

API_URL = "https://eco.taobao.com/router/rest"
SEED_CSV = Path(__file__).resolve().parents[3] / "data" / "companies" / "seed.csv"
MOCK_PAGE_SIZE = 20
MOCK_CATEGORIES = ["无线蓝牙耳机", "家用破壁机", "酱油礼盒", "智能手机", "扫地机器人", "智能手表", "休闲零食"]


def build_params(method: str, appkey: str, secret: str, extra: dict) -> dict:
    """构造淘宝开放平台请求参数并计算 MD5 签名。"""
    params = {
        "method": method,
        "app_key": appkey,
        "timestamp": str(int(time.time())),
        "format": "json",
        "v": "2.0",
        "sign_method": "md5",
        **extra,
    }
    text = "".join(f"{k}{params[k]}" for k in sorted(params))
    params["sign"] = hashlib.md5((secret + text + secret).encode()).hexdigest().upper()
    return params


def _mock_brand_pool() -> list[str]:
    """mock 品牌池从 seed.csv 动态取样（避免与种子数据漂移）。"""
    try:
        import csv
        with open(SEED_CSV, encoding="utf-8") as f:
            keys = [r["key"] for r in csv.DictReader(f) if r.get("key")]
        return keys or ["示例品牌"]
    except OSError:
        return ["示例品牌"]


class MallClient:
    def __init__(self, mode: str, appkey: str = "", secret: str = ""):
        self.mode = mode
        self.appkey = appkey
        self.secret = secret
        if mode == "taobao" and not (appkey and secret):
            raise RuntimeError(
                "mall_mode=taobao 需要配置 TAOBAO_APPKEY/TAOBAO_SECRET；"
                "开发联调请设 MALL_MODE=mock")

    @property
    def is_mock_mode(self) -> bool:
        return self.mode == "mock"

    async def search(self, keyword: str, page_no: int = 1, page_size: int = 20) -> list[dict]:
        if self.mode == "mock":
            return self._mock(keyword, page_no, page_size)
        params = build_params(
            "taobao.tbk.dg.material.optional", self.appkey, self.secret,
            {
                "q": keyword,
                "adzone_id": settings.taobao_adzone_id,
                "page_no": page_no,
                "page_size": page_size,
            },
        )
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(API_URL, data=params)
        data = resp.json()
        result = data.get("tbk_dg_material_optional_response", {}).get("result_list", {}).get("map_data", [])
        return [self._normalize_item(it) for it in result]

    def _normalize_item(self, it: dict) -> dict:
        return {
            "item_id": str(it.get("num_iid", "")),
            "title": it.get("title", ""),
            "image": it.get("pict_url", ""),
            "price": float(it.get("zk_final_price", 0) or 0),
            "brand": it.get("brand_name", "") or "",
            "category": it.get("level_one_category_name", "") or "",
            "click_url": it.get("click_url", ""),
        }

    def _mock(self, keyword: str, page_no: int, page_size: int) -> list[dict]:
        """开发模式演示商品：标题嵌入真实品牌，验证 搜索→打标→排序 全链路。"""
        pool = _mock_brand_pool()
        rng = random.Random(keyword + str(page_no))
        items = []
        for i in range(page_size):
            brand = rng.choice(pool)
            cat = rng.choice(MOCK_CATEGORIES)
            price = round(rng.uniform(49, 1999), 2)
            items.append({
                "item_id": f"mock-{abs(hash(keyword + str(page_no) + str(i))) % 10**9}",
                "title": f"{brand}官方旗舰店 {cat} 新款促销（双十一预热）",
                "image": "",
                "price": price,
                "brand": brand,
                "category": cat,
                "click_url": f"https://example.com/buy/{brand}",
            })
        return items


mall_client = MallClient(
    settings.mall_mode, settings.taobao_appkey, settings.taobao_secret)