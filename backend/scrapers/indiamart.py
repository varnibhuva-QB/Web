import re
import json
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from urllib.parse import quote_plus, urlencode


# ─── Driver Setup ─────────────────────────────────────────────────────────────

def get_driver():
    options = webdriver.ChromeOptions()
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1400,900")
    options.add_argument("--lang=en-US,en")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    driver = webdriver.Chrome(options=options)
    driver.execute_script(
        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    )
    return driver


# ─── Helpers ──────────────────────────────────────────────────────────────────

def safe_text(el, by, selector, default=""):
    try:
        return el.find_element(by, selector).text.strip()
    except Exception:
        return default


def safe_attr(el, by, selector, attr, default=""):
    try:
        return el.find_element(by, selector).get_attribute(attr) or default
    except Exception:
        return default


def clean_phone(raw):
    raw = re.sub(r"(Call|Phone|Tel|Mobile|Mob)[:\s]*", "", raw, flags=re.IGNORECASE)
    return raw.strip().split("\n")[0].strip()


# ─── CAPTCHA Detection & Wait ─────────────────────────────────────────────────

CAPTCHA_SIGNALS = [
    "captcha", "robot", "verify you are human",
    "are you a robot", "unusual traffic", "security check",
    "please verify", "access denied", "blocked"
]

def is_captcha_page(driver):
    """Return True if the current page looks like a CAPTCHA / block page."""
    try:
        body = driver.find_element(By.TAG_NAME, "body").text.lower()
        title = driver.title.lower()
        combined = body[:2000] + title          # only check top of page for speed
        return any(sig in combined for sig in CAPTCHA_SIGNALS)
    except Exception:
        return False


def wait_for_captcha_solve(driver, keyword, location, page_num, timeout=300):
    """
    Pause scraping, focus the Chrome window so the user can see the CAPTCHA,
    and wait until the CAPTCHA page is gone (user solved it manually).
    Returns True once scraping can resume, False on timeout.
    """
    print("\n" + "="*60)
    print("⚠️  CAPTCHA / BLOCK PAGE DETECTED!")
    print("   Please solve the CAPTCHA in the Chrome window.")
    print("   Scraping will resume automatically after you solve it.")
    print("="*60 + "\n")

    # Bring the browser window to front
    try:
        driver.maximize_window()
    except Exception:
        pass

    deadline = time.time() + timeout
    while time.time() < deadline:
        time.sleep(3)
        if not is_captcha_page(driver):
            # Page changed — check it now has real results
            try:
                cards = driver.find_elements(By.CSS_SELECTOR, "div.mGSbox, div.supplierBox, a.lcname")
                if cards:
                    print("✅ CAPTCHA solved! Resuming scrape...\n")
                    return True
                # Might be on a blank page — navigate back to correct search page
                navigate_to_page(driver, keyword, location, page_num)
                time.sleep(4)
                if not is_captcha_page(driver):
                    print("✅ CAPTCHA solved! Resuming scrape...\n")
                    return True
            except Exception:
                pass

    print("⏱️  CAPTCHA wait timed out. Stopping scrape.")
    return False


def check_captcha_and_wait(driver, keyword, location, page_num):
    """Call this before processing each page. Returns False if we should abort."""
    if is_captcha_page(driver):
        return wait_for_captcha_solve(driver, keyword, location, page_num)
    return True


# ─── URL Builder ──────────────────────────────────────────────────────────────

def build_search_url(keyword, location, page=1):
    """
    IndiaMart search URL structure (verified):
      https://www.indiamart.com/search.mp?ss=KEYWORD&pref_loc=LOCATION&page=N
    
    The `pref_loc` param filters by city/state.
    The `ss` param is the search keyword.
    """
    params = {
        "ss":       keyword.strip(),
        "pref_loc": location.strip(),
    }
    if page > 1:
        params["page"] = page
    return "https://www.indiamart.com/search.mp?" + urlencode(params)


def navigate_to_page(driver, keyword, location, page_num):
    url = build_search_url(keyword, location, page_num)
    print(f"[indiamart] Navigating → {url}")
    driver.get(url)
    time.sleep(5)
    dismiss_popups(driver)


# ─── Popup Dismissal ──────────────────────────────────────────────────────────

def dismiss_popups(driver):
    for xpath in [
        "//button[@id='closeBannerBtn']",
        "//button[contains(@class,'cls-btn')]",
        "//button[contains(@class,'close')]",
        "//span[contains(@class,'close') and not(ancestor::nav)]",
        "//div[contains(@class,'modal')]//button",
    ]:
        try:
            el = driver.find_element(By.XPATH, xpath)
            if el.is_displayed():
                el.click()
                time.sleep(0.8)
        except Exception:
            pass


# ─── Card Extraction ──────────────────────────────────────────────────────────

def extract_card(card):
    record = {
        "company_name":  "",
        "contact_person": "",
        "phone":         "",
        "address":       "",
        "product":       "",
        "business_type": "",
        "website":       "",
        "source":        "IndiaMart",
    }

    phone_re = re.compile(r"[\+\d][\d\s\-\(\)]{6,}\d")

    # ── Company name ──────────────────────────────────────────────────────────
    for sel in [
        (By.CSS_SELECTOR, "a.lcname"),
        (By.CSS_SELECTOR, "div.companyname a"),
        (By.CSS_SELECTOR, "span.companyname"),
        (By.CSS_SELECTOR, ".company-name a"),
        (By.CSS_SELECTOR, "h2.companyname a"),
        (By.CSS_SELECTOR, "a[href*='indiamart.com']"),
    ]:
        name = safe_text(card, *sel)
        if name and len(name) > 2:
            record["company_name"] = name
            break

    # ── Product ───────────────────────────────────────────────────────────────
    for sel in [
        (By.CSS_SELECTOR, "a.prd-name"),
        (By.CSS_SELECTOR, ".prd-name"),
        (By.CSS_SELECTOR, "div.product-title a"),
        (By.CSS_SELECTOR, "h3 a"),
        (By.CSS_SELECTOR, "h3"),
        (By.CSS_SELECTOR, "h2 a"),
    ]:
        prd = safe_text(card, *sel)
        if prd and len(prd) > 2:
            record["product"] = prd
            break

    # ── Address ───────────────────────────────────────────────────────────────
    for sel in [
        (By.CSS_SELECTOR, "span.contadd"),
        (By.CSS_SELECTOR, ".company-location"),
        (By.CSS_SELECTOR, "span.add"),
        (By.CSS_SELECTOR, "div.address"),
        (By.XPATH,        ".//span[contains(@class,'contadd')]"),
        (By.XPATH,        ".//div[contains(@class,'location')]"),
    ]:
        addr = safe_text(card, *sel)
        if addr and len(addr) > 3:
            record["address"] = addr
            break

    # ── Phone — 3-tier strategy ───────────────────────────────────────────────

    # Tier 1: data attributes (IndiaMart pre-loads phone here)
    for attr in ["data-mobile", "data-phone", "data-mob", "data-contact"]:
        for el in card.find_elements(By.XPATH, f".//*[@{attr}]"):
            val = el.get_attribute(attr) or ""
            if phone_re.search(val):
                record["phone"] = val.strip()
                break
        if record["phone"]:
            break

    # Tier 2: tel: href
    if not record["phone"]:
        for el in card.find_elements(By.XPATH, ".//a[contains(@href,'tel:')]"):
            val = (el.get_attribute("href") or "").replace("tel:", "").strip()
            if phone_re.search(val):
                record["phone"] = val
                break

    # Tier 3: visible text
    if not record["phone"]:
        for sel in [
            (By.CSS_SELECTOR, "span.phone"),
            (By.CSS_SELECTOR, ".contact-number"),
            (By.CSS_SELECTOR, "div.callnow"),
            (By.CSS_SELECTOR, "span.callnow"),
            (By.XPATH,        ".//span[contains(@class,'call')]"),
            (By.XPATH,        ".//span[contains(text(),'+91')]"),
            (By.XPATH,        ".//div[contains(@class,'phone')]"),
        ]:
            raw = safe_text(card, *sel)
            cleaned = clean_phone(raw)
            if cleaned and phone_re.search(cleaned):
                record["phone"] = cleaned
                break

    # ── Contact person ────────────────────────────────────────────────────────
    for sel in [
        (By.CSS_SELECTOR, "span.contact-name"),
        (By.CSS_SELECTOR, ".person-name"),
        (By.CSS_SELECTOR, "span.cname"),
        (By.XPATH,        ".//span[contains(@class,'contact')]"),
    ]:
        person = safe_text(card, *sel)
        if person and len(person) > 2:
            record["contact_person"] = person
            break

    # ── Business type ─────────────────────────────────────────────────────────
    for sel in [
        (By.CSS_SELECTOR, "span.btype"),
        (By.CSS_SELECTOR, ".business-type"),
        (By.XPATH,
         ".//span[contains(text(),'Manufacturer') or contains(text(),'Supplier')"
         " or contains(text(),'Exporter') or contains(text(),'Trader')"
         " or contains(text(),'Wholesaler') or contains(text(),'Retailer')]"),
    ]:
        btype = safe_text(card, *sel)
        if btype:
            record["business_type"] = btype
            break

    # ── Company profile / website URL ─────────────────────────────────────────
    for sel in [
        (By.CSS_SELECTOR, "a.lcname"),
        (By.CSS_SELECTOR, "div.companyname a"),
        (By.CSS_SELECTOR, "a[href*='indiamart.com']"),
        (By.XPATH, ".//a[contains(@href,'http') and (contains(text(),'Website') or contains(@href,'http'))]"),
    ]:
        href = safe_attr(card, *sel, "href")
        if href and href.startswith("http"):
            if "indiamart.com" in href and "search" not in href:
                record["website"] = href
                break
            if record["website"] == "" or record["website"] is None:
                record["website"] = href

    # Final fallback for website text within the card
    if not record["website"]:
        for sel in [
            (By.CSS_SELECTOR, "span.website"),
            (By.XPATH, ".//span[contains(text(),'www.') or contains(text(),'http') or contains(text(),'.')]"),
        ]:
            raw = safe_text(card, *sel)
            if raw and raw.startswith("http"):
                record["website"] = raw.strip()
                break

    return record


# ─── Card Selector Discovery ─────────────────────────────────────────────────

CARD_SELECTORS = [
    "div.mGSbox",
    "div.supplierBox",
    "div.supplier-data",
    "div.product-unit",
    "li.productListing",
    "div.prd-info-block",
    "div.prd-prc-block",
    "div[data-id]",
]

def find_cards(driver):
    for sel in CARD_SELECTORS:
        cards = driver.find_elements(By.CSS_SELECTOR, sel)
        if len(cards) >= 2:          # at least 2 to avoid false positives
            print(f"[indiamart] ✓ Card selector: '{sel}' → {len(cards)} cards")
            return cards
    # Last-resort fallback
    cards = driver.find_elements(
        By.XPATH,
        "//div[.//a[contains(@href,'indiamart.com') "
        "and not(contains(@href,'search')) "
        "and not(contains(@href,'indiamart.com/'))]]"
    )
    if cards:
        print(f"[indiamart] ✓ Fallback XPath → {len(cards)} cards")
    return cards


# ─── Next Page ────────────────────────────────────────────────────────────────

def go_to_next_page(driver):
    try:
        btn = driver.find_element(
            By.XPATH,
            "//a[contains(@class,'next') and not(contains(@class,'disabled'))]"
            " | //li[contains(@class,'next') and not(contains(@class,'disabled'))]/a"
            " | //a[@rel='next']"
            " | //a[normalize-space(text())='Next' or normalize-space(text())='›']"
        )
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", btn)
        time.sleep(0.5)
        btn.click()
        time.sleep(4)
        return True
    except Exception:
        return False


# ─── Main Scraper ─────────────────────────────────────────────────────────────

def scrape_indiamart(keyword, location, max_results=20, progress_callback=None):
    driver = get_driver()
    wait   = WebDriverWait(driver, 20)

    page_num = 1
    navigate_to_page(driver, keyword, location, page_num)

    # Verify the URL actually applied keyword + location
    current = driver.current_url
    print(f"[indiamart] Landed on: {current}")
    print(f"[indiamart] Searching: keyword='{keyword}'  location='{location}'")

    results = []
    seen    = set()

    while len(results) < max_results:

        # ── CAPTCHA guard ─────────────────────────────────────────────────────
        if not check_captcha_and_wait(driver, keyword, location, page_num):
            break   # User didn't solve in time — abort cleanly

        print(f"\n[indiamart] ── Page {page_num} ── scraped so far: {len(results)} ──")

        cards = find_cards(driver)
        if not cards:
            print("[indiamart] No cards found. Stopping.")
            break

        for card in cards:
            if len(results) >= max_results:
                break

            # CAPTCHA can appear mid-page too (lazy-load triggers)
            if is_captcha_page(driver):
                if not wait_for_captcha_solve(driver, keyword, location, page_num):
                    break
                cards = find_cards(driver)   # refresh card list after resume
                break                        # restart this page's loop

            try:
                record = extract_card(card)
                if not record["company_name"]:
                    continue

                key = record["company_name"].lower().strip()
                if key in seen:
                    continue
                seen.add(key)

                # Pack extras into the `data` JSON column
                record["data"] = json.dumps({
                    "keyword":        keyword,
                    "location":       location,
                    "business_type":  record.pop("business_type", ""),
                    "contact_person": record.pop("contact_person", ""),
                    "product":        record.pop("product", ""),
                    "page":           page_num,
                    "profile_url":    record.get("website", ""),
                })

                results.append(record)
                print(f"  [{len(results):>3}] {record['company_name']}"
                      f"  |  {record['phone'] or '—'}"
                      f"  |  {record['address'] or '—'}")

                if progress_callback:
                    progress_callback(record, len(results))

            except Exception as e:
                print(f"[indiamart] Card parse error: {e}")
                continue

        if len(results) >= max_results:
            break

        # ── Next page ─────────────────────────────────────────────────────────
        if not go_to_next_page(driver):
            # Try URL-based navigation as fallback
            page_num += 1
            navigate_to_page(driver, keyword, location, page_num)
            if is_captcha_page(driver):
                if not wait_for_captcha_solve(driver, keyword, location, page_num):
                    break
            # Check if we got a real page
            new_cards = find_cards(driver)
            if not new_cards:
                print("[indiamart] No more pages. Done.")
                break
        else:
            page_num += 1
            time.sleep(1)

        # Small human-like delay between pages
        time.sleep(2)

    driver.quit()
    print(f"\n[indiamart] ✅ Finished. Total results: {len(results)}")
    return results


# ─── Standalone test ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 50)
    print("   IndiaMart Scraper")
    print("=" * 50)
    keyword  = input("Keyword  (e.g. steel pipe)   : ").strip()
    location = input("Location (e.g. Ahmedabad)    : ").strip()
    max_r    = int(input("Max results (default 20)     : ").strip() or "20")
    print()

    data = scrape_indiamart(keyword, location, max_results=max_r)

    print(f"\n{'─'*60}")
    print(f"  Total results : {len(data)}")
    print(f"{'─'*60}")
    for r in data:
        extra = json.loads(r.get("data", "{}"))
        print(f"  Company  : {r['company_name']}")
        print(f"  Phone    : {r['phone'] or '—'}")
        print(f"  Address  : {r['address'] or '—'}")
        print(f"  Product  : {extra.get('product','—')}")
        print(f"  Type     : {extra.get('business_type','—')}")
        print(f"  Contact  : {extra.get('contact_person','—')}")
        print(f"  Profile  : {r['website'] or '—'}")
        print()