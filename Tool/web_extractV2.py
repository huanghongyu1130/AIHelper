#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
web_extractV2.py
單檔版 FastMCP 伺服器：提供「全文抽取（含連結）」的 web_extract_tool
優化版：全域瀏覽器實例、隱蹤模式、內容過濾
"""

from __future__ import annotations

import os
import re
import json
import asyncio
import logging
from typing import Any, Literal
from urllib.parse import urljoin, urlparse

from pydantic import BaseModel, Field
from bs4 import BeautifulSoup, NavigableString
from fastmcp import FastMCP
from playwright.async_api import async_playwright, Browser, Playwright, BrowserContext, Page

# ---- 抽全文工具：trafilatura / ReadabiliPy ----
from trafilatura import extract
from trafilatura.settings import Extractor
from readabilipy import simple_json_from_html_string
from markdownify import markdownify as md

# 設定日誌
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# =========================
# 參數配置
# =========================
HEADLESS = os.getenv("HEADLESS", "1") != "0"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
BLOCK_TYPES = {"image", "media", "font", "stylesheet"}
CONSENT_SELECTORS = [
    'text="同意"', 'text="接受"', 'text="同意所有"', 'text="我同意"',
    'text="I agree"', 'text="Accept all"', '[id*="accept"]',
    '[class*="consent"] button', '[aria-label*="accept"]',
]

# =========================
# 資料模型
# =========================
class LinkItem(BaseModel):
    text: str = ""
    href: str

class ExtractResult(BaseModel):
    title: str | None = None
    url: str
    final_url: str | None = None
    mode: Literal["article", "hub"] | None = None
    content: str = Field(..., description="Markdown 格式的主要內容")
    links: list[LinkItem] = []
    metadata: dict | None = None
    error: str | None = None

# =========================
# 全域瀏覽器管理 (Singleton)
# =========================
class BrowserManager:
    _playwright: Playwright | None = None
    _browser: Browser | None = None
    _lock: asyncio.Lock = asyncio.Lock()

    @classmethod
    async def get_browser(cls) -> Browser:
        async with cls._lock:
            if cls._browser is None:
                logger.info("Initializing global browser instance...")
                cls._playwright = await async_playwright().start()
                cls._browser = await cls._playwright.chromium.launch(
                    headless=HEADLESS,
                    args=[
                        "--disable-blink-features=AutomationControlled",
                        "--no-sandbox",
                        "--disable-setuid-sandbox"
                    ]
                )
            return cls._browser

    @classmethod
    async def close(cls):
        async with cls._lock:
            if cls._browser:
                await cls._browser.close()
                cls._browser = None
            if cls._playwright:
                await cls._playwright.stop()
                cls._playwright = None
            logger.info("Global browser instance closed.")

# =========================
# Playwright 邏輯
# =========================
async def prepare_page(page: Page) -> None:
    """隱蹤與前置處理：隱藏 webdriver 屬性、處理彈窗、懶載入滾動。"""
    # 反爬蟲：移除 navigator.webdriver
    await page.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined
        });
    """)

    try:
        # 嘗試點擊同意按鈕 (Timeout 設短一點避免卡住)
        for sel in CONSENT_SELECTORS:
            try:
                btn = await page.query_selector(sel)
                if btn:
                    if await btn.is_visible():
                        await btn.click(timeout=500)
                        break
            except Exception:
                pass
    except Exception:
        pass

    # 簡單滾動觸發懶加載
    try:
        await page.evaluate(
            """() => new Promise(res=>{
                let i=0;
                const step=()=>{
                    window.scrollBy(0, 800);
                    i++;
                    if(i<5) requestAnimationFrame(step); else res();
                };
                step();
            })"""
        )
        await asyncio.sleep(1) # 等待滾動後的內容加載
    except Exception:
        pass

async def fetch_html(url: str) -> tuple[str, str, str | None]:
    """獲取渲染後的 HTML (重用瀏覽器)。"""
    browser = await BrowserManager.get_browser()
    # 每個請求使用獨立 Context 以隔離 Cookie/Storage
    context = await browser.new_context(
        user_agent=USER_AGENT,
        viewport={"width": 1366, "height": 768},
        locale="zh-TW"
    )
    
    # 攔截不必要的資源請求
    await context.route(
        "**/*",
        lambda r: (r.abort() if r.request.resource_type in BLOCK_TYPES else r.continue_()),
    )

    page = await context.new_page()
    final_url = url
    title = None
    html = ""
    
    try:
        # 漸進式載入策略
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=15000)
            await page.wait_for_load_state("networkidle", timeout=5000)
        except Exception:
            # 如果 networkidle 超時，通常 domcontentloaded 已經好了，可以接受
            pass

        await prepare_page(page)
        
        final_url = page.url
        title = await page.title()
        html = await page.content()
        
    except Exception as e:
        logger.error(f"Error fetching {url}: {e}")
        raise e
    finally:
        await context.close()
        
    return html, final_url, title

# =========================
# 內容處理邏輯
# =========================
def is_article_like(soup: BeautifulSoup) -> bool:
    """判斷是否為文章頁面。"""
    # 1. 檢查 meta type
    meta_og = soup.find("meta", property="og:type")
    if meta_og and meta_og.get("content", "").lower() in {"article", "news", "blog"}:
        return True
        
    # 2. 檢查 schema.org
    for s in soup.select('script[type="application/ld+json"]'):
        try:
            text = s.string
            if not text: continue
            data = json.loads(text)
            arr = data if isinstance(data, list) else [data]
            for obj in arr:
                t = obj.get("@type")
                types = set(t if isinstance(t, list) else ([t] if t else []))
                if {"NewsArticle", "BlogPosting", "Article"} & types:
                    return True
        except:
            continue
            
    # 3. 檢查常見文章標籤
    if soup.find("article"):
        return True
        
    return False

def clean_links(links: list[LinkItem], base_url: str) -> list[LinkItem]:
    """過濾並排序連結。"""
    unique_map = {}
    base_domain = urlparse(base_url).netloc
    
    for item in links:
        href = item.href
        text = item.text
        
        # 基礎過濾
        if not href or not text: continue
        if len(text) < 2: continue # 太短的連結通常無意義
        
        # 排除非 HTTP 連結
        if not href.startswith("http"): continue
        
        # 排除功能性連結
        low_href = href.lower()
        if any(x in low_href for x in ["javascript:", "mailto:", "tel:", "/login", "/signup", "/cart", "comment", "share"]):
            continue
            
        # 排除錨點 (同頁跳轉)
        if "#" in href:
            href = href.split("#")[0]
            if href == base_url or href == base_url + "/":
                continue

        # 簡單計分排序
        score = 0
        parsed = urlparse(href)
        path = parsed.path.lower()
        
        # 站內連結優先
        if parsed.netloc == base_domain:
            score += 1
            
        # 文章特徵
        if re.search(r"/\d{4}/\d{1,2}/", path) or re.search(r"/(news|article|blog|p|post)/", path):
            score += 2
            
        # 標題長度適中
        if 5 <= len(text) <= 50:
            score += 1
            
        # 更新最佳匹配 (同一 URL 保留文字較長或較有意義的)
        if href not in unique_map or len(text) > len(unique_map[href][0]):
            unique_map[href] = (text, score)

    # 轉回 List 並排序
    result = [LinkItem(text=v[0], href=k) for k, v in unique_map.items()]
    # 依分數降序
    result.sort(key=lambda x: unique_map[x.href][1], reverse=True)
    return result[:80] # 限制返回數量

# =========================
# MCP 伺服器
# =========================
mcp = FastMCP(name="WebFullExtractMCP")

@mcp.tool(name="web_extract_tool")
async def web_extract_tool(
    url: str = Field(..., description="目標網頁連結")
):
    """
    智能網頁全文抽取工具。
    會自動切換為「文章模式」或「索引頁模式」，並過濾廣告與雜訊。
    返回結構包含：標題、Markdown 正文、與正文相關的精選連結。
    """
    try:
        html, final_url, title = await fetch_html(url)
    except Exception as e:
        return ExtractResult(url=url, content="", error=f"Fetch failed: {str(e)}").model_dump()

    if not html:
        return ExtractResult(url=url, content="", error="Empty HTML response").model_dump()

    base_url = final_url or url
    soup = BeautifulSoup(html, "html.parser")
    is_article = is_article_like(soup)
    
    # 1. 嘗試使用 Trafilatura (通常效果最好)
    md_text = extract(
        html,
        include_links=True,
        include_images=False,
        include_formatting=True,
        url=base_url
    )
    
    meta = {}
    try:
        # 提取 Metadata
        xtr = Extractor(output_format="json", with_metadata=True)
        meta_json = extract(html, options=xtr, include_links=False, url=base_url)
        if meta_json:
            meta = json.loads(meta_json)
    except:
        pass

    # 2. 如果 Trafilatura 失敗，使用 ReadabiliPy fallback
    if not md_text or len(md_text) < 100:
        try:
            sj = simple_json_from_html_string(html, use_readability=True)
            content_html = sj.get("content")
            if content_html:
                md_text = md(content_html)
                if not title: title = sj.get("title")
        except:
            pass

    # 3. 如果還是空的，直接把 body 轉 markdown (最糟情況)
    if not md_text:
        body = soup.body
        if body:
            # 移除顯著的雜訊
            for tag in body.select("script, style, nav, footer, iframe, form"):
                tag.decompose()
            md_text = md(str(body))
    
    # 連結提取策略
    # 如果是文章，主要依賴正文內的連結 (Trafilatura 已經包含在 md 中，但我們也可以額外列出)
    # 如果是首頁 (Hub)，則需要從 HTML 中提取列表
    
    raw_links = []
    # 從原始 HTML 提取所有連結做後處理
    for a in soup.select("a[href]"):
        h = urljoin(base_url, a.get("href", "").strip())
        t = " ".join(a.get_text().split())
        if h and t:
            raw_links.append(LinkItem(text=t, href=h))
            
    filtered_links = clean_links(raw_links, base_url)
    
    # 最終標題確認
    final_title = title or meta.get("title") or (soup.title.string if soup.title else "")
    
    return ExtractResult(
        title=final_title,
        url=url,
        final_url=final_url,
        mode="article" if is_article else "hub",
        content=md_text or "(No Content Extracted)",
        links=filtered_links,
        metadata=meta
    ).model_dump()

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", "-p", type=int, required=True, default=8021)
    args = parser.parse_args()
    
    print(f"Starting MCP Web Extract Server on port {args.port}...")
    # 注意：FastMCP 的 run_sse_async 會接管 Event Loop
    # 我們不在此顯式呼叫 startup，依賴 Tool 內的 Lazy Loading
    asyncio.run(mcp.run_http_async(host="0.0.0.0", port=args.port))