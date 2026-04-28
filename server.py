"""
港股金融数据 MCP Server

提供港股实时行情、历史K线、财务指标等数据查询功能。
数据源: akshare (东方财富 / 新浪)
"""

import json
import akshare as ak
import pandas as pd
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("港股金融数据", instructions="港股行情、财务数据查询服务")


def _to_scalar(val):
    if hasattr(val, "item"):
        return val.item()
    return val


def _fmt(val, suffix=""):
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return "N/A"
    val = _to_scalar(val)
    if isinstance(val, float) and suffix == "%":
        return f"{round(val, 2)}%"
    if suffix:
        return f"{val}{suffix}"
    return val if not isinstance(val, float) else round(val, 3)


def _get_hk_daily(symbol: str, limit: int = 5):
    """获取港股日线数据"""
    code = symbol.strip().upper().zfill(5)
    df = ak.stock_hk_daily(symbol=code, adjust="")
    if df is None or df.empty:
        return None, code
    df = df.sort_values("date", ascending=False).reset_index(drop=True)
    return df.head(limit), code


# ---------- Tool 1: 实时行情 ----------

@mcp.tool()
def get_hk_quote(symbol: str) -> str:
    """获取港股实时行情，包含最新价、涨跌幅、成交量等

    Args:
        symbol: 港股代码，如 0700 (腾讯控股), 9988 (阿里巴巴)
    """
    try:
        df, code = _get_hk_daily(symbol, 5)
        if df is None:
            return json.dumps({"error": f"未找到 {code}"}, ensure_ascii=False)

        latest = df.iloc[0]
        prev = df.iloc[1] if len(df) > 1 else latest
        change = round(float(latest["close"]) - float(prev["close"]), 3)
        change_pct = (change / float(prev["close"])) * 100 if float(prev["close"]) != 0 else 0

        result = {
            "代码": f"{symbol.upper().zfill(5)}.HK",
            "日期": str(latest["date"])[:10],
            "最新价": round(float(latest["close"]), 3),
            "涨跌额": round(change, 3),
            "涨跌幅": f"{round(change_pct, 2)}%",
            "最高": round(float(latest["high"]), 3),
            "最低": round(float(latest["low"]), 3),
            "开盘": round(float(latest["open"]), 3),
            "前收盘": round(float(prev["close"]), 3),
            "成交量": int(latest["volume"]),
            "成交额": _fmt(latest.get("amount")),
        }
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"error": f"查询失败: {str(e)}"}, ensure_ascii=False)


# ---------- Tool 2: 历史K线 ----------

@mcp.tool()
def get_hk_history(symbol: str, days: int = 30) -> str:
    """获取港股历史日K线数据

    Args:
        symbol: 港股代码，如 0700 (腾讯控股), 9988 (阿里巴巴)
        days: 返回最近几天数据，默认30天
    """
    try:
        df, code = _get_hk_daily(symbol, days)
        if df is None:
            return json.dumps({"error": f"未找到 {code}"}, ensure_ascii=False)

        records = []
        for _, row in df.iterrows():
            records.append({
                "日期": str(row["date"])[:10],
                "开盘": float(row["open"]),
                "最高": float(row["high"]),
                "最低": float(row["low"]),
                "收盘": float(row["close"]),
                "成交量": int(row["volume"]),
            })

        return json.dumps({
            "代码": f"{symbol.upper().zfill(5)}.HK",
            "数据条数": len(records),
            "数据": records,
        }, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"error": f"查询失败: {str(e)}"}, ensure_ascii=False)


# ---------- Tool 3: 公司信息 ----------

@mcp.tool()
def get_hk_company_info(symbol: str) -> str:
    """获取港股公司详细信息

    Args:
        symbol: 港股代码，如 0700 (腾讯控股), 9988 (阿里巴巴)
    """
    try:
        code = symbol.strip().upper().zfill(5)
        df = ak.stock_hk_company_profile_em(symbol=code)
        if df is None or df.empty:
            return json.dumps({"error": f"未找到 {code}"}, ensure_ascii=False)

        row = df.iloc[0]
        result = {
            "代码": code,
            "名称": _fmt(row.get("公司名称")),
            "英文名": _fmt(row.get("英文名称")),
            "行业": _fmt(row.get("所属行业")),
            "董事长": _fmt(row.get("董事长")),
            "员工数": _fmt(row.get("员工人数")),
            "主营业务": (_fmt(row.get("公司介绍")) or "")[:500],
            "网址": _fmt(row.get("公司网址")),
        }
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"error": f"查询失败: {str(e)}"}, ensure_ascii=False)


# ---------- Tool 4: 核心财务指标 ----------

@mcp.tool()
def get_hk_key_metrics(symbol: str) -> str:
    """获取港股核心财务指标，含 PE、PB、ROE、市值、利润率等

    Args:
        symbol: 港股代码，如 0700 (腾讯控股), 9988 (阿里巴巴)
    """
    try:
        code = symbol.strip().upper().zfill(5)
        df = ak.stock_hk_financial_indicator_em(symbol=code)
        if df is None or df.empty:
            return json.dumps({"error": f"未找到 {code}"}, ensure_ascii=False)

        row = df.iloc[0]
        result = {
            "代码": code,
            "估值指标": {
                "市盈率 (PE)": _fmt(row.get("市盈率")),
                "市净率 (PB)": _fmt(row.get("市净率")),
                "总市值": _fmt(row.get("总市值(港元)")),
                "股息率": _fmt(row.get("股息率TTM(%)"), "%"),
                "派息比率": _fmt(row.get("派息比率(%)"), "%"),
            },
            "盈利指标": {
                "基本每股收益": _fmt(row.get("基本每股收益(元)"), "元"),
                "每股净资产": _fmt(row.get("每股净资产(元)"), "元"),
                "股东权益回报率 (ROE)": _fmt(row.get("股东权益回报率(%)"), "%"),
                "总资产回报率 (ROA)": _fmt(row.get("总资产回报率(%)"), "%"),
                "销售净利率": _fmt(row.get("销售净利率(%)"), "%"),
            },
            "经营数据": {
                "营业总收入": _fmt(row.get("营业总收入")),
                "净利润": _fmt(row.get("净利润")),
                "营收增长": _fmt(row.get("营业总收入滚动环比增长(%)"), "%"),
                "净利润增长": _fmt(row.get("净利润滚动环比增长(%)"), "%"),
            },
        }
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"error": f"查询失败: {str(e)}"}, ensure_ascii=False)


# ---------- Tool 5: 技术面分析 ----------

@mcp.tool()
def get_hk_price_analysis(symbol: str) -> str:
    """获取港股技术分析，含均线、成交量分析

    Args:
        symbol: 港股代码，如 0700 (腾讯控股), 9988 (阿里巴巴)
    """
    try:
        df, code = _get_hk_daily(symbol, 60)
        if df is None:
            return json.dumps({"error": f"未找到 {code}"}, ensure_ascii=False)

        closes = df["close"].astype(float).values
        volumes = df["volume"].astype(float).values
        latest_close = float(closes[0])

        def ma(n):
            return round(float(closes[:n].mean()), 3) if len(closes) >= n else None

        ma5, ma10, ma20 = ma(5), ma(10), ma(20)
        avg_vol_5 = float(volumes[:5].mean())

        result = {
            "代码": f"{symbol.upper().zfill(5)}.HK",
            "日期": str(df.iloc[0]["date"])[:10],
            "收盘价": latest_close,
            "均线": {
                "MA5": ma5,
                "MA10": ma10,
                "MA20": ma20,
            },
            "偏离均线": {
                "距MA5": f"{round((latest_close/ma5-1)*100, 2)}%" if ma5 else "N/A",
                "距MA10": f"{round((latest_close/ma10-1)*100, 2)}%" if ma10 else "N/A",
                "距MA20": f"{round((latest_close/ma20-1)*100, 2)}%" if ma20 else "N/A",
            },
            "成交量": {
                "当日": int(volumes[0]),
                "近5日均量": int(avg_vol_5),
                "量比": round(volumes[0] / avg_vol_5, 2) if avg_vol_5 > 0 else "N/A",
            },
        }
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"error": f"查询失败: {str(e)}"}, ensure_ascii=False)


if __name__ == "__main__":
    mcp.run(transport="stdio")
