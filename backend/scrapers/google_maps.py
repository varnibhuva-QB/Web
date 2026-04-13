import re
import json
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from urllib.parse import quote_plus


def get_driver():
    options = webdriver.ChromeOptions()
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1400,900")
    options.add_argument("--lang=en-US,en")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    driver = webdriver.Chrome(options=options)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    return driver


def scroll_panel(driver):
    """Scroll the left results panel to load more listings."""
    try:
        panel = driver.find_element(By.XPATH, '//div[@role="feed"]')
        driver.execute_script("arguments[0].scrollTop += 2000;", panel)
    except Exception:
        driver.execute_script("window.scrollBy(0, 2000);")
    time.sleep(2)


def extract_details(driver, wait):
    """Extract all details from the currently open listing panel."""
    data = {
        "business_name": "",
        "address": "",
        "phone": "",
        "website": "",
        "rating": "",
        "category": "",
    }

    # Wait for detail panel to load
    try:
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "h1.DUwDvf, h1.fontHeadlineLarge, h1")))
    except TimeoutException:
        pass
    time.sleep(2)

    page = driver.page_source

    # ── Name ──────────────────────────────────────────────────────────────────
    for sel in ["h1.DUwDvf", "h1.fontHeadlineLarge", "h1"]:
        try:
            name = driver.find_element(By.CSS_SELECTOR, sel).text.strip()
            if name:
                data["business_name"] = name
                break
        except Exception:
            pass

    # ── Category ──────────────────────────────────────────────────────────────
    for sel in ["button.DkEaL", "span.YhemCb", ".mgr77e span"]:
        try:
            cat = driver.find_element(By.CSS_SELECTOR, sel).text.strip()
            if cat:
                data["category"] = cat
                break
        except Exception:
            pass

    # ── Rating ────────────────────────────────────────────────────────────────
    for sel in ["div.fontDisplayLarge", "span.ceNzKf", "span.kvMYJc"]:
        try:
            r = driver.find_element(By.CSS_SELECTOR, sel).text.strip()
            if r and re.match(r"^\d[\d.]*$", r):
                data["rating"] = r
                break
        except Exception:
            pass

    # ── Address ───────────────────────────────────────────────────────────────
    for xpath in [
        "//button[@data-item-id='address']//div[contains(@class,'Io6YTe')]",
        "//button[@data-item-id='address']",
        "//button[contains(@aria-label,'Address')]//div[contains(@class,'Io6YTe')]",
        "//button[contains(@aria-label,'Address')]",
    ]:
        try:
            addr = driver.find_element(By.XPATH, xpath).text.strip()
            if addr and len(addr) > 5:
                data["address"] = addr
                break
        except Exception:
            pass

    # Fallback: regex on page source
    if not data["address"]:
        match = re.search(r'"address":"([^"]{10,})"', page)
        if match:
            data["address"] = match.group(1)

    # ── Phone ─────────────────────────────────────────────────────────────────
    phone_re = re.compile(r"[\+\d][\d\s\-\(\)\.]{6,}\d")
    for xpath in [
        "//button[contains(@data-item-id,'phone:tel')]//div[contains(@class,'Io6YTe')]",
        "//button[contains(@data-item-id,'phone')]//div[contains(@class,'Io6YTe')]",
        "//button[contains(@data-item-id,'phone')]",
        "//button[contains(@aria-label,'Phone')]//div[contains(@class,'Io6YTe')]",
        "//button[contains(@aria-label,'Phone')]",
        "//a[contains(@href,'tel:')]",
    ]:
        try:
            els = driver.find_elements(By.XPATH, xpath)
            for el in els:
                txt = el.text.strip() or el.get_attribute("href") or ""
                txt = txt.replace("tel:", "").strip()
                if phone_re.search(txt):
                    data["phone"] = txt
                    break
            if data["phone"]:
                break
        except Exception:
            pass

    # ── Website ───────────────────────────────────────────────────────────────
    for xpath in [
        "//a[contains(@data-item-id,'authority')]",
        "//a[@data-value='Website']",
        "//a[contains(@aria-label,'Website')]",
        "//a[contains(@href,'http') and not(contains(@href,'google'))]",
    ]:
        try:
            els = driver.find_elements(By.XPATH, xpath)
            for el in els:
                href = el.get_attribute("href") or ""
                if href and "google.com" not in href and "goo.gl" not in href:
                    data["website"] = href
                    break
            if data["website"]:
                break
        except Exception:
            pass

    return data


def scrape_google_maps(keyword, location, max_results=20, progress_callback=None):
    driver = get_driver()
    wait = WebDriverWait(driver, 20)

    query = quote_plus(f"{keyword} {location}")
    url = f"https://www.google.com/maps/search/{query}/"
    driver.get(url)
    time.sleep(4)

    # Dismiss consent / cookie popups if any
    for btn_text in ["Accept all", "Reject all", "I agree", "Accept"]:
        try:
            btn = driver.find_element(By.XPATH, f"//button[contains(.,'{btn_text}')]")
            btn.click()
            time.sleep(1)
            break
        except Exception:
            pass

    # Wait for listings to appear
    try:
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "a.hfpxzc")))
    except TimeoutException:
        print("[scraper] Listings did not load. Check your keyword/location.")

    time.sleep(3)

    results = []
    seen_names = set()
    processed = 0
    no_new_count = 0

    while len(results) < max_results:
        listings = driver.find_elements(By.CSS_SELECTOR, "a.hfpxzc")

        if processed >= len(listings):
            scroll_panel(driver)
            new_listings = driver.find_elements(By.CSS_SELECTOR, "a.hfpxzc")
            if len(new_listings) == len(listings):
                no_new_count += 1
                if no_new_count >= 3:
                    print("[scraper] No more results to load.")
                    break
            else:
                no_new_count = 0
            listings = new_listings

        if processed >= len(listings):
            break

        try:
            listing = listings[processed]
            processed += 1

            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", listing)
            time.sleep(0.5)

            try:
                listing.click()
            except Exception:
                driver.execute_script("arguments[0].click();", listing)

            try:
                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "h1")))
            except TimeoutException:
                pass
            time.sleep(2.5)

            detail = extract_details(driver, wait)

            name = detail.get("business_name", "").strip()
            if not name or name in seen_names:
                continue
            if not any([detail["address"], detail["phone"], detail["website"]]):
                continue

            seen_names.add(name)

            record = {
                "business_name": name,
                "address": detail["address"],
                "phone": detail["phone"],
                "website": detail["website"],
                "source": "Google Maps",
                "data": json.dumps({
                    "keyword": keyword,
                    "location": location,
                    "rating": detail["rating"],
                    "category": detail["category"],
                    "maps_url": driver.current_url,
                }),
            }
            results.append(record)
            print(f"[{len(results)}] {name} | {detail['phone']} | {detail['address']}")

            if progress_callback:
                progress_callback(record, len(results))

            if len(results) >= max_results:
                break

        except Exception as e:
            print(f"[scraper] Error on listing {processed}: {e}")
            continue

    driver.quit()
    return results


# ── Standalone test ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    keyword  = input("Keyword  (e.g. restaurant): ").strip()
    location = input("Location (e.g. Ahmedabad) : ").strip()
    max_r    = int(input("Max results              : ").strip() or "10")

    data = scrape_google_maps(keyword, location, max_results=max_r)
    print(f"\n✅ Done. Total scraped: {len(data)}")
    for r in data:
        print(r)