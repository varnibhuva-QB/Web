import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException
import pandas as pd
import time
import random
import re
from threading import Lock
import asyncio
from playwright.async_api import async_playwright
import traceback

class HybridScraper:
    def __init__(self, max_workers=5):
        # Selenium driver for GoodFirms
        self.selenium_driver = None
        self.wait = None
        
        # Playwright for websites
        self.playwright = None
        self.browser = None
        
        # Results storage
        self.results = []
        self.results_lock = Lock()
        self.request_count = 0
        self.session_start = time.time()
        self.max_workers = max_workers

    def check_rate_limit(self):
        """Pause if making too many requests"""
        self.request_count += 1
        
        # Every 30 requests, take a longer break
        if self.request_count % 30 == 0:
            pause_time = random.uniform(30, 45)
            print(f"\n⏸ Taking a {int(pause_time)}s break to avoid rate limiting...")
            time.sleep(pause_time)
            print(f"⏯ Resuming scraping...\n")
        
        # Every 100 requests, take an even longer break
        elif self.request_count % 100 == 0:
            pause_time = random.uniform(60, 90)
            print(f"\n⏸ Extended break: {int(pause_time)}s to avoid detection...")
            time.sleep(pause_time)
            print(f"⏯ Resuming scraping...\n")

    def init_selenium_driver(self):
        """Initialize Selenium driver for GoodFirms (always headed)"""
        try:
            print("🔧 Initializing Selenium for GoodFirms (HEADED mode)...")
            options = uc.ChromeOptions()
            options.add_argument("--start-maximized")
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-web-security")
            options.add_argument("--disable-features=IsolateOrigins,site-per-process")
            options.add_argument(f"user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36")
            
            # Randomize window size slightly
            window_width = random.randint(1920, 1940)
            window_height = random.randint(1080, 1100)
            options.add_argument(f"--window-size={window_width},{window_height}")
            
            # Set preferences
            prefs = {
                "profile.default_content_setting_values.notifications": 2,
                "credentials_enable_service": False,
                "profile.password_manager_enabled": False
            }
            options.add_experimental_option("prefs", prefs)
            
            # Initialize driver
            self.selenium_driver = uc.Chrome(
                version_main=144,
                options=options,
                use_subprocess=True
            )
            
            self.wait = WebDriverWait(self.selenium_driver, 15)
            
            # Execute stealth scripts
            self.selenium_driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            self.selenium_driver.execute_script("Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]})")
            self.selenium_driver.execute_script("Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']})")
            
            print("✓ Selenium browser initialized")
            print("✓ Anti-ban protections enabled")
            return True
            
        except Exception as e:
            print(f"✗ Selenium initialization failed: {e}")
            print("\n💡 Solution:")
            print("  1. Update Chrome to latest version")
            print("  2. Or run: pip install --upgrade undetected-chromedriver")
            return False

    async def init_playwright(self):
        """Initialize Playwright for parallel website scraping"""
        try:
            print("\n🎭 Initializing Playwright for websites (HEADLESS mode)...")
            self.playwright = await async_playwright().start()
            
            # Launch browser with stealth settings
            self.browser = await self.playwright.chromium.launch(
                headless=True,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-dev-shm-usage',
                    '--no-sandbox',
                    '--disable-web-security',
                ]
            )
            
            print(f"✓ Playwright initialized")
            print(f"✓ Ready for {self.max_workers} parallel contexts")
            return True
            
        except Exception as e:
            print(f"✗ Playwright initialization failed: {e}")
            print("\n💡 Solution:")
            print("  Run: playwright install chromium")
            return False

    def human_delay(self, min_sec=2, max_sec=4):
        """Random human-like delay"""
        delay = random.uniform(min_sec, max_sec)
        if random.random() < 0.1:
            delay += random.uniform(2, 5)
        time.sleep(delay)

    def is_valid_website_url(self, url):
        """Check if URL is valid"""
        if not url or url == "Not Available":
            return False
        
        url_lower = url.lower()
        invalid_patterns = [
            "cloudflare.com", "javascript:", "#", "goodfirms.co",
            "linkedin.com", "facebook.com", "twitter.com", 
            "instagram.com", "youtube.com"
        ]
        
        for pattern in invalid_patterns:
            if pattern in url_lower:
                return False
        
        if not url.startswith(("http://", "https://")):
            return False
        
        return True

    def extract_website_from_card(self, card):
        """Extract website URL from company card using Selenium"""
        website = "Not Available"
        
        try:
            # Method 1: Look for "Visit Website" button
            try:
                visit_btn = card.find_element(By.XPATH, ".//a[contains(text(), 'Visit Website') or contains(@title, 'Visit Website') or contains(@class, 'visit-website')]")
                href = visit_btn.get_attribute("href")
                if self.is_valid_website_url(href):
                    website = href
                    return website
            except:
                pass
            
            # Method 2: Look for external links
            try:
                links = card.find_elements(By.TAG_NAME, "a")
                for link in links:
                    href = link.get_attribute("href") or ""
                    text = link.text.lower().strip()
                    title = (link.get_attribute("title") or "").lower()
                    
                    if "goodfirms.co" in href.lower():
                        continue
                    
                    if "visit" in text or "website" in text or "visit" in title or "website" in title:
                        if self.is_valid_website_url(href):
                            website = href
                            return website
            except:
                pass
            
            # Method 3: Check data attributes
            try:
                card_html = card.get_attribute('outerHTML')
                website_match = re.search(r'data-website=["\']([^"\']+)["\']', card_html)
                if website_match:
                    url = website_match.group(1)
                    if self.is_valid_website_url(url):
                        website = url
                        return website
            except:
                pass
                
        except Exception as e:
            pass
        
        return website

    async def extract_emails_playwright(self, page):
        """Extract emails using Playwright"""
        all_emails = set()
        
        try:
            # Get page text with timeout
            try:
                page_text = await asyncio.wait_for(page.inner_text('body'), timeout=5)
            except asyncio.TimeoutError:
                return all_emails
            
            # Method 1: Get mailto links
            try:
                mailto_links = await asyncio.wait_for(
                    page.query_selector_all('a[href^="mailto:"]'), 
                    timeout=3
                )
                for link in mailto_links[:15]:
                    try:
                        href = await asyncio.wait_for(link.get_attribute('href'), timeout=1)
                        email = href.replace('mailto:', '').split('?')[0].strip().lower()
                        if '@' in email and len(email) < 100:
                            all_emails.add(email)
                    except:
                        continue
            except asyncio.TimeoutError:
                pass
            
            # Method 2: Regex patterns
            email_patterns = [
                r'\b[A-Za-z0-9][A-Za-z0-9._%+-]{0,63}@[A-Za-z0-9][A-Za-z0-9.-]{0,253}\.[A-Za-z]{2,}\b',
                r'\b[A-Za-z0-9._%+-]+@(?:[A-Za-z0-9-]+\.)+[A-Za-z]{2,}\b',
                r'\b[A-Za-z0-9._%+-]+\s*@\s*[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b',
            ]
            
            for pattern in email_patterns:
                emails_found = re.findall(pattern, page_text, re.IGNORECASE)
                for email in emails_found:
                    email = email.strip().replace(' ', '').lower()
                    if '@' in email and len(email) < 100:
                        all_emails.add(email)
            
            # Method 3: Look in contact sections
            try:
                contact_sections = await asyncio.wait_for(
                    page.query_selector_all('[class*="contact"], [class*="email"], [id*="contact"], [id*="email"]'),
                    timeout=3
                )
                for section in contact_sections[:10]:
                    try:
                        section_text = await asyncio.wait_for(section.inner_text(), timeout=2)
                        emails = re.findall(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b', section_text, re.IGNORECASE)
                        for email in emails:
                            email = email.strip().lower()
                            if len(email) < 100:
                                all_emails.add(email)
                    except:
                        continue
            except asyncio.TimeoutError:
                pass
                
        except Exception as e:
            pass
        
        # Filter emails
        valid_emails = set()
        exclude_terms = [
            'example.com', 'test.com', 'domain.com', 'yourcompany',
            'sampleemail', 'youremail', 'email.com', 'sample.com',
            'tempmail', 'fakeemail', 'noreply@', 'no-reply@',
            'donotreply@', '@example', '@test', 'wixpress.com',
            'placeholder', 'yourmail', '@sentry.io', '@wix.com'
        ]
        
        for email in all_emails:
            if len(email) < 5 or len(email) > 80:
                continue
            if any(term in email.lower() for term in exclude_terms):
                continue
            if email.count('@') != 1:
                continue
            domain = email.split('@')[1]
            if '.' not in domain or len(domain) < 4:
                continue
            valid_emails.add(email)
        
        return valid_emails

    async def extract_phones_playwright(self, page):
        """Extract phone numbers using Playwright"""
        all_phones = set()
        
        try:
            # Get page text with timeout
            try:
                page_text = await asyncio.wait_for(page.inner_text('body'), timeout=5)
            except asyncio.TimeoutError:
                return all_phones
            
            # Method 1: Get tel links
            try:
                tel_links = await asyncio.wait_for(
                    page.query_selector_all('a[href^="tel:"]'),
                    timeout=3
                )
                for link in tel_links[:15]:
                    try:
                        href = await asyncio.wait_for(link.get_attribute('href'), timeout=1)
                        phone = href.replace('tel:', '').strip()
                        phone = re.sub(r'[^\d+\-\s()]', '', phone)
                        if '+91' in phone or phone.replace(' ', '').replace('-', '').startswith('91'):
                            all_phones.add(phone)
                    except:
                        continue
            except asyncio.TimeoutError:
                pass
            
            # Method 2: Regex patterns
            phone_patterns = [
                r'\+91[\s-]?\d{5}[\s-]?\d{5}',
                r'\+91[\s-]?\d{4}[\s-]?\d{6}',
                r'\+91[\s-]?\d{3}[\s-]?\d{7}',
                r'\+91[\s-]?\d{10}',
                r'\+91\s?\(\d{3,5}\)[\s-]?\d{5,7}',
                r'91[\s-]\d{5}[\s-]?\d{5}',
                r'91[\s-]\d{10}',
                r'91\s?\(\d{3,5}\)[\s-]?\d{5,7}',
                r'0\d{2,4}[\s-]?\d{6,8}',
                r'\(0\d{2,4}\)[\s-]?\d{6,8}',
                r'\b[6-9]\d{9}\b',
                r'\(\+91\)[\s-]?\d{10}',
                r'\(91\)[\s-]?\d{10}',
            ]
            
            for pattern in phone_patterns:
                phones_found = re.findall(pattern, page_text)
                for phone in phones_found:
                    all_phones.add(phone.strip())
            
            # Method 3: Look in contact sections
            try:
                contact_sections = await asyncio.wait_for(
                    page.query_selector_all('[class*="contact"], [class*="phone"], [id*="contact"], [id*="phone"]'),
                    timeout=3
                )
                for section in contact_sections[:10]:
                    try:
                        section_text = await asyncio.wait_for(section.inner_text(), timeout=2)
                        for pattern in phone_patterns:
                            phones = re.findall(pattern, section_text)
                            for phone in phones:
                                all_phones.add(phone.strip())
                    except:
                        continue
            except asyncio.TimeoutError:
                pass
                
        except Exception as e:
            pass
        
        # Validate phones
        valid_phones = []
        for phone in all_phones:
            digits = re.sub(r'[^\d+]', '', phone)
            if len(digits) < 10 or len(digits) > 13:
                continue
            
            if digits.startswith('+91'):
                if len(digits) == 13:
                    valid_phones.append(phone)
            elif digits.startswith('91'):
                if len(digits) == 12:
                    valid_phones.append(phone)
            elif digits.startswith('0'):
                if 10 <= len(digits) <= 11:
                    valid_phones.append(phone)
            elif digits[0] in '6789':
                if len(digits) == 10:
                    valid_phones.append(phone)
        
        return valid_phones

    async def extract_key_person_playwright(self, page):
        """Extract key person using Playwright"""
        key_person_name = "Not Available"
        key_person_email = "Not Available"
        key_person_title = "Not Available"
        
        try:
            # Get page text with timeout
            try:
                page_text = await asyncio.wait_for(page.inner_text('body'), timeout=5)
            except asyncio.TimeoutError:
                return key_person_name, key_person_email, key_person_title
            
            # Method 1: Look in team/about sections
            try:
                team_sections = await asyncio.wait_for(
                    page.query_selector_all(
                        '[class*="team"], [class*="leadership"], [class*="management"], '
                        '[class*="about"], [class*="founder"], [id*="team"], [id*="leadership"], [id*="about"]'
                    ),
                    timeout=3
                )
                
                for section in team_sections[:8]:
                    try:
                        section_text = await asyncio.wait_for(section.inner_text(), timeout=2)
                        
                        person_patterns = [
                            r'(?:CEO|Chief Executive Officer|Founder|Co-Founder|Managing Director|Director|President|Owner|Proprietor|Partner)[:\s\-–—,]+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})',
                            r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})[,\s\-–—]+(?:CEO|Chief Executive Officer|Founder|Co-Founder|Managing Director|Director|President|Owner|Proprietor|Partner)',
                            r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})\s*\((?:CEO|Chief Executive Officer|Founder|Co-Founder|Managing Director|Director|President|Owner|Proprietor|Partner)\)',
                            r'(?:CEO|Chief Executive Officer|Founder|Co-Founder|Managing Director|Director|President|Owner|Proprietor|Partner)\s*[-–—]\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})',
                            r'(?:Mr\.|Mrs\.|Ms\.|Dr\.)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})(?:\s*[,\-–—]\s*(?:CEO|Founder|Director|Managing Director|President|Owner))?',
                        ]
                        
                        for pattern in person_patterns:
                            matches = re.findall(pattern, section_text, re.IGNORECASE | re.MULTILINE)
                            if matches:
                                for match in matches[:3]:
                                    name = match.strip() if isinstance(match, str) else match[0].strip()
                                    name_parts = name.split()
                                    
                                    if 2 <= len(name_parts) <= 4 and 5 < len(name) < 50:
                                        if all(part[0].isupper() for part in name_parts):
                                            false_positives = ['Privacy Policy', 'Terms Conditions', 'Contact Us', 
                                                             'About Us', 'Our Team', 'Get Started', 'Learn More', 
                                                             'View More', 'Read More', 'Click Here', 'Find Out']
                                            
                                            if name not in false_positives and not any(fp in name for fp in false_positives):
                                                key_person_name = name
                                                
                                                # Extract title
                                                title_match = re.search(
                                                    r'(CEO|Chief Executive Officer|Founder|Co-Founder|Managing Director|Director|President|Owner|Proprietor|Partner)',
                                                    section_text[max(0, section_text.find(name)-50):section_text.find(name)+100],
                                                    re.IGNORECASE
                                                )
                                                if title_match:
                                                    key_person_title = title_match.group(1)
                                                
                                                # Find email near name
                                                try:
                                                    context_start = max(0, section_text.find(name) - 100)
                                                    context_end = min(len(section_text), section_text.find(name) + 200)
                                                    context = section_text[context_start:context_end]
                                                    
                                                    email_match = re.search(
                                                        r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b',
                                                        context
                                                    )
                                                    if email_match:
                                                        email = email_match.group(0).lower()
                                                        if not any(generic in email for generic in ['info@', 'contact@', 'support@', 'sales@', 'hello@']):
                                                            key_person_email = email
                                                except:
                                                    pass
                                                
                                                if key_person_name != "Not Available":
                                                    return key_person_name, key_person_email, key_person_title
                    except:
                        continue
            except asyncio.TimeoutError:
                pass
            
            # Method 2: Check structured data
            if key_person_name == "Not Available":
                try:
                    scripts = await asyncio.wait_for(
                        page.query_selector_all('script[type="application/ld+json"]'),
                        timeout=2
                    )
                    for script in scripts:
                        try:
                            content = await asyncio.wait_for(script.inner_text(), timeout=1)
                            founder_match = re.search(r'"(?:founder|author|creator|name)"\s*:\s*"([^"]+)"', content, re.IGNORECASE)
                            if founder_match:
                                name = founder_match.group(1).strip()
                                if 2 <= len(name.split()) <= 4 and 5 < len(name) < 50:
                                    key_person_name = name
                                    return key_person_name, key_person_email, "Founder"
                        except:
                            continue
                except asyncio.TimeoutError:
                    pass
            
            # Method 3: Look in headings
            if key_person_name == "Not Available":
                try:
                    headings = await asyncio.wait_for(
                        page.query_selector_all('h1, h2, h3, h4'),
                        timeout=2
                    )
                    for heading in headings[:20]:
                        try:
                            heading_text = await asyncio.wait_for(heading.inner_text(), timeout=1)
                            if re.search(r'\b(CEO|Founder|Director|Managing Director|President|Owner)\b', heading_text, re.IGNORECASE):
                                parent = await heading.evaluate_handle('element => element.parentElement')
                                parent_text = await asyncio.wait_for(parent.inner_text(), timeout=1)
                                
                                name_match = re.search(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})\b', parent_text)
                                if name_match:
                                    name = name_match.group(1).strip()
                                    if 2 <= len(name.split()) <= 4 and 5 < len(name) < 50:
                                        key_person_name = name
                                        
                                        title_match = re.search(
                                            r'(CEO|Chief Executive Officer|Founder|Co-Founder|Managing Director|Director|President|Owner)',
                                            parent_text,
                                            re.IGNORECASE
                                        )
                                        if title_match:
                                            key_person_title = title_match.group(1)
                                        
                                        return key_person_name, key_person_email, key_person_title
                        except:
                            continue
                except asyncio.TimeoutError:
                    pass
                    
        except Exception as e:
            pass
        
        return key_person_name, key_person_email, key_person_title

    async def scrape_website_playwright(self, context, website_url, company_name, worker_id):
        """Scrape a single website using Playwright context"""
        print(f"[Worker-{worker_id}] → Visiting: {website_url[:50]}...")
        
        contact_data = {
            "Email": "Not Available",
            "Phone": "Not Available",
            "Key Person": "Not Available",
            "Key Person Title": "Not Available",
            "Key Person Email": "Not Available"
        }
        
        page = None
        try:
            # Create new page in context
            page = await context.new_page()
            
            # Set viewport
            await page.set_viewport_size({"width": 1920, "height": 1080})
            
            # Navigate to website with timeout
            try:
                await asyncio.wait_for(
                    page.goto(website_url, wait_until='domcontentloaded'),
                    timeout=30
                )
            except asyncio.TimeoutError:
                print(f"[Worker-{worker_id}] ✗ Page load timeout - skipping")
                return contact_data
            
            await asyncio.sleep(random.uniform(2, 4))
            
            # Check for Cloudflare
            url = page.url.lower()
            if "cloudflare.com" in url:
                print(f"[Worker-{worker_id}] ⚠ Cloudflare protection - skipping")
                return contact_data
            
            try:
                title = await asyncio.wait_for(page.title(), timeout=3)
                if "just a moment" in title.lower() or "challenge" in title.lower():
                    print(f"[Worker-{worker_id}] ⚠ Cloudflare challenge - skipping")
                    return contact_data
            except:
                pass
            
            # Scroll page with timeout
            try:
                await asyncio.wait_for(
                    page.evaluate("window.scrollTo(0, document.body.scrollHeight/3)"),
                    timeout=2
                )
                await asyncio.sleep(1)
                await asyncio.wait_for(
                    page.evaluate("window.scrollTo(0, document.body.scrollHeight/2)"),
                    timeout=2
                )
                await asyncio.sleep(1)
            except:
                pass
            
            # Extract from main page
            print(f"[Worker-{worker_id}] → Scanning main page...")
            try:
                all_emails = await asyncio.wait_for(
                    self.extract_emails_playwright(page),
                    timeout=10
                )
                all_phones = await asyncio.wait_for(
                    self.extract_phones_playwright(page),
                    timeout=10
                )
            except asyncio.TimeoutError:
                print(f"[Worker-{worker_id}] ⚠ Main page extraction timeout")
                all_emails = set()
                all_phones = []
            
            # Try to visit contact page
            contact_page_visited = False
            try:
                print(f"[Worker-{worker_id}] → Looking for Contact page...")
                links = await asyncio.wait_for(page.query_selector_all('a'), timeout=5)
                
                for link in links[:50]:
                    try:
                        href = await asyncio.wait_for(link.get_attribute('href'), timeout=1)
                        href = href or ''
                        
                        text_elem = await asyncio.wait_for(link.inner_text(), timeout=1)
                        text = text_elem.lower().strip() if text_elem else ''
                        
                        if any(kw in text or kw in href.lower() for kw in ['contact', 'reach us', 'get in touch']):
                            # Check visibility with timeout
                            try:
                                is_visible = await asyncio.wait_for(link.is_visible(), timeout=2)
                            except asyncio.TimeoutError:
                                continue
                            
                            if is_visible:
                                print(f"[Worker-{worker_id}] → Clicking Contact page...")
                                try:
                                    # Click and wait for navigation with timeout
                                    await asyncio.wait_for(link.click(timeout=5000), timeout=10)
                                    await asyncio.sleep(2)
                                except asyncio.TimeoutError:
                                    print(f"[Worker-{worker_id}] ⚠ Contact page click timeout - skipping")
                                    continue
                                except Exception:
                                    continue
                                
                                contact_page_visited = True
                                
                                # Extract from contact page with timeout
                                try:
                                    contact_emails = await asyncio.wait_for(
                                        self.extract_emails_playwright(page),
                                        timeout=10
                                    )
                                    contact_phones = await asyncio.wait_for(
                                        self.extract_phones_playwright(page),
                                        timeout=10
                                    )
                                    all_emails.update(contact_emails)
                                    all_phones.extend(contact_phones)
                                except asyncio.TimeoutError:
                                    print(f"[Worker-{worker_id}] ⚠ Contact extraction timeout")
                                
                                print(f"[Worker-{worker_id}] ✓ Contact page scanned")
                                break
                    except:
                        continue
            except asyncio.TimeoutError:
                print(f"[Worker-{worker_id}] ⚠ Contact page search timeout")
            except Exception:
                pass
            
            # Try to visit about/team page
            try:
                if contact_page_visited:
                    try:
                        await asyncio.wait_for(
                            page.goto(website_url, wait_until='domcontentloaded'),
                            timeout=20
                        )
                        await asyncio.sleep(random.uniform(2, 3))
                    except asyncio.TimeoutError:
                        print(f"[Worker-{worker_id}] ⚠ Return to main page timeout")
                
                print(f"[Worker-{worker_id}] → Looking for About/Team page...")
                links = await asyncio.wait_for(page.query_selector_all('a'), timeout=5)
                
                for link in links[:50]:
                    try:
                        href = await asyncio.wait_for(link.get_attribute('href'), timeout=1)
                        href = href or ''
                        
                        text_elem = await asyncio.wait_for(link.inner_text(), timeout=1)
                        text = text_elem.lower().strip() if text_elem else ''
                        
                        if any(kw in text or kw in href.lower() for kw in ['about', 'team', 'leadership', 'our team', 'management', 'founders']):
                            try:
                                is_visible = await asyncio.wait_for(link.is_visible(), timeout=2)
                            except asyncio.TimeoutError:
                                continue
                            
                            if is_visible:
                                print(f"[Worker-{worker_id}] → Clicking About/Team page...")
                                try:
                                    await asyncio.wait_for(link.click(timeout=5000), timeout=10)
                                    await asyncio.sleep(2)
                                except asyncio.TimeoutError:
                                    print(f"[Worker-{worker_id}] ⚠ About page click timeout - skipping")
                                    continue
                                except Exception:
                                    continue
                                
                                # Extract key person with timeout
                                try:
                                    key_person_name, key_person_email, key_person_title = await asyncio.wait_for(
                                        self.extract_key_person_playwright(page),
                                        timeout=10
                                    )
                                    if key_person_name != "Not Available":
                                        contact_data["Key Person"] = key_person_name
                                        contact_data["Key Person Title"] = key_person_title
                                        contact_data["Key Person Email"] = key_person_email
                                except asyncio.TimeoutError:
                                    print(f"[Worker-{worker_id}] ⚠ Key person extraction timeout")
                                
                                print(f"[Worker-{worker_id}] ✓ About/Team page scanned")
                                break
                    except:
                        continue
            except asyncio.TimeoutError:
                print(f"[Worker-{worker_id}] ⚠ About page search timeout")
            except Exception:
                pass
            
            # If no key person found, try main page
            if contact_data["Key Person"] == "Not Available":
                try:
                    if contact_page_visited:
                        try:
                            await asyncio.wait_for(
                                page.goto(website_url, wait_until='domcontentloaded'),
                                timeout=20
                            )
                            await asyncio.sleep(random.uniform(2, 3))
                        except asyncio.TimeoutError:
                            pass
                    
                    key_person_name, key_person_email, key_person_title = await asyncio.wait_for(
                        self.extract_key_person_playwright(page),
                        timeout=10
                    )
                    contact_data["Key Person"] = key_person_name
                    contact_data["Key Person Title"] = key_person_title
                    contact_data["Key Person Email"] = key_person_email
                except asyncio.TimeoutError:
                    pass
                except:
                    pass
            
            # Process emails
            if all_emails:
                priority_prefixes = ['info@', 'contact@', 'hello@', 'support@', 'sales@', 'inquiry@', 'mail@']
                avoid_prefixes = ['noreply@', 'no-reply@', 'donotreply@']
                
                filtered_emails = [e for e in all_emails if not any(avoid in e for avoid in avoid_prefixes)]
                
                if filtered_emails:
                    priority_emails = [e for e in filtered_emails if any(prefix in e for prefix in priority_prefixes)]
                    contact_data["Email"] = priority_emails[0] if priority_emails else filtered_emails[0]
                    print(f"[Worker-{worker_id}] ✓ Email: {contact_data['Email']}")
            
            # Process phones
            if all_phones:
                plus_91_phones = [p for p in all_phones if p.startswith('+91')]
                contact_data["Phone"] = plus_91_phones[0] if plus_91_phones else all_phones[0]
                print(f"[Worker-{worker_id}] ✓ Phone: {contact_data['Phone']}")
            
            # Display key person
            if contact_data["Key Person"] != "Not Available":
                print(f"[Worker-{worker_id}] ✓ Key Person: {contact_data['Key Person']} ({contact_data['Key Person Title']})")
                if contact_data["Key Person Email"] != "Not Available":
                    print(f"[Worker-{worker_id}] ✓ Key Person Email: {contact_data['Key Person Email']}")
        
        except asyncio.TimeoutError:
            print(f"[Worker-{worker_id}] ✗ Overall timeout")
        except Exception as e:
            print(f"[Worker-{worker_id}] ✗ Error: {str(e)[:80]}")
        finally:
            if page:
                try:
                    await asyncio.wait_for(page.close(), timeout=5)
                except:
                    pass
        
        return contact_data

    async def scrape_websites_parallel(self, companies_list):
        """Scrape multiple websites in parallel using Playwright"""
        print(f"\n{'='*60}")
        print(f"Scraping {len(companies_list)} websites with {self.max_workers} parallel workers")
        print(f"{'='*60}\n")
        
        # Create browser contexts (one per worker)
        contexts = []
        for i in range(self.max_workers):
            context = await self.browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36'
            )
            contexts.append(context)
        
        # Process companies in batches
        batch_size = self.max_workers
        for batch_start in range(0, len(companies_list), batch_size):
            batch = companies_list[batch_start:batch_start + batch_size]
            tasks = []
            
            for i, company_info in enumerate(batch):
                context = contexts[i % self.max_workers]
                worker_id = (i % self.max_workers) + 1
                
                idx = company_info["idx"]
                total = company_info["total"]
                name = company_info["name"]
                website = company_info["website"]
                location = company_info["location"]
                
                print(f"\n[{idx}/{total}] [Worker-{worker_id}] {name[:50]}")
                
                company_data = {
                    "Company Name": name,
                    "Website": website,
                    "Email": "Not Available",
                    "Phone": "Not Available",
                    "City": location.split(",")[0].strip() if location != "Not Available" else "Not Available",
                    "Address": location,
                    "Key Person": "Not Available",
                    "Key Person Title": "Not Available",
                    "Key Person Email": "Not Available"
                }
                
                if website != "Not Available":
                    print(f"[Worker-{worker_id}] ✓ Website: {website[:60]}")
                    task = self.scrape_website_playwright(context, website, name, worker_id)
                    tasks.append((task, company_data))
                else:
                    print(f"[Worker-{worker_id}] ⚠ No website available")
                    with self.results_lock:
                        self.results.append(company_data)
            
            # Wait for all tasks in batch to complete with overall timeout
            if tasks:
                try:
                    results = await asyncio.wait_for(
                        asyncio.gather(*[task for task, _ in tasks], return_exceptions=True),
                        timeout=180  # 3 minutes max per batch
                    )
                    
                    for result, (_, company_data) in zip(results, tasks):
                        if isinstance(result, dict):
                            gf_address = company_data["Address"]
                            gf_city = company_data["City"]
                            company_data.update(result)
                            company_data["Address"] = gf_address
                            company_data["City"] = gf_city
                        
                        with self.results_lock:
                            self.results.append(company_data)
                except asyncio.TimeoutError:
                    print(f"\n⚠ Batch timeout - saving partial results and continuing...")
                    # Save whatever completed
                    for result, (_, company_data) in zip(results if 'results' in locals() else [], tasks):
                        if isinstance(result, dict):
                            gf_address = company_data["Address"]
                            gf_city = company_data["City"]
                            company_data.update(result)
                            company_data["Address"] = gf_address
                            company_data["City"] = gf_city
                        with self.results_lock:
                            self.results.append(company_data)
            
            # Save progress every 20 companies
            if (batch_start + batch_size) % 20 == 0:
                self.save_results(f"progress_checkpoint_{batch_start + batch_size}.xlsx")
                print(f"\n💾 Progress saved at {batch_start + batch_size} companies")
            
            # Delay between batches
            await asyncio.sleep(15)
        
        # Close contexts
        for context in contexts:
            await context.close()

    def collect_companies_selenium(self, start_page, end_page):
        """Collect company data from GoodFirms using Selenium"""
        base_url = "https://www.goodfirms.co/directory/languages/top-software-development-companies?sid=22"
        
        print(f"\n{'='*60}")
        print(f"Opening GoodFirms (Pages {start_page} to {end_page})...")
        print(f"Using Selenium (HEADED mode)")
        print(f"{'='*60}\n")
        
        self.selenium_driver.get(base_url)
        print("⏳ Please solve CAPTCHA if present...")
        print("   Waiting 30 seconds...\n")
        time.sleep(30)
        
        company_data_list = []
        
        print(f"\n{'='*60}")
        print(f"Collecting company data from pages {start_page} to {end_page}")
        print(f"{'='*60}\n")
        
        for page_num in range(start_page, end_page + 1):
            print(f"📄 Page {page_num}/{end_page}...")
            
            try:
                if page_num > start_page:
                    current_url = self.selenium_driver.current_url
                    if '?page=' in current_url or '&page=' in current_url:
                        next_url = re.sub(r'[?&]page=\d+', f'&page={page_num}', current_url)
                    else:
                        separator = '&' if '?' in current_url else '?'
                        next_url = f"{current_url}{separator}page={page_num}"
                    
                    self.selenium_driver.get(next_url)
                    self.human_delay(3, 5)
                
                self.wait.until(EC.presence_of_element_located((By.CLASS_NAME, "firm-wrapper")))
                self.human_delay(2, 3)
                
                cards = self.selenium_driver.find_elements(By.CLASS_NAME, "firm-wrapper")
                
                for card in cards:
                    try:
                        name = card.find_element(By.CSS_SELECTOR, ".firm-name, h3").text.strip()
                        
                        location = "Not Available"
                        try:
                            location = card.find_element(By.CSS_SELECTOR, ".firm-location span").text.strip()
                        except:
                            pass
                        
                        website = self.extract_website_from_card(card)
                        
                        if name:
                            company_data_list.append({
                                "name": name,
                                "website": website,
                                "location": location
                            })
                    except:
                        continue
                
                print(f"   ✓ Collected {len(company_data_list)} companies so far")
                
            except Exception as e:
                print(f"   ✗ Error on page {page_num}: {str(e)[:50]}")
                break
        
        print(f"\n✓ Total companies collected: {len(company_data_list)}\n")
        return company_data_list

    async def run(self, start_page, end_page):
        """Main async run method"""
        # Initialize Selenium for GoodFirms
        if not self.init_selenium_driver():
            print("Failed to initialize Selenium!")
            return
        
        # Collect companies using Selenium
        companies_list = self.collect_companies_selenium(start_page, end_page)
        
        if not companies_list:
            print("❌ No companies found!")
            return
        
        # Initialize Playwright for websites
        if not await self.init_playwright():
            print("Failed to initialize Playwright!")
            return
        
        # Prepare companies for parallel scraping
        companies_for_scraping = []
        for idx, company in enumerate(companies_list, 1):
            companies_for_scraping.append({
                "idx": idx,
                "total": len(companies_list),
                "name": company["name"],
                "website": company["website"],
                "location": company["location"]
            })
        
        # Scrape websites in parallel using Playwright
        await self.scrape_websites_parallel(companies_for_scraping)
        
        # Save final results
        filename = f"GoodFirms_Pages_{start_page}_to_{end_page}.xlsx"
        self.save_results(filename)
        self.show_statistics()

    def save_results(self, filename):
        """Save results to Excel"""
        with self.results_lock:
            if self.results:
                df = pd.DataFrame(self.results)
                column_order = [
                    "Company Name", "Website", "Email", "Phone",
                    "City", "Address", "Key Person", "Key Person Title",
                    "Key Person Email"
                ]
                df = df[column_order]
                df.to_excel(filename, index=False)
                print(f"✓ Saved to: {filename}")

    def show_statistics(self):
        """Display extraction statistics"""
        if not self.results:
            return
        
        total = len(self.results)
        websites = sum(1 for c in self.results if c['Website'] != 'Not Available')
        emails = sum(1 for c in self.results if c['Email'] != 'Not Available')
        phones = sum(1 for c in self.results if c['Phone'] != 'Not Available')
        addresses = sum(1 for c in self.results if c['Address'] != 'Not Available')
        key_people = sum(1 for c in self.results if c['Key Person'] != 'Not Available')
        key_emails = sum(1 for c in self.results if c['Key Person Email'] != 'Not Available')
        
        print(f"\n{'='*60}")
        print("📊 FINAL STATISTICS")
        print(f"{'='*60}")
        print(f"Total Companies: {total}")
        print(f"Websites: {websites} ({websites*100//total if total > 0 else 0}%)")
        print(f"Emails: {emails} ({emails*100//total if total > 0 else 0}%)")
        print(f"Phones: {phones} ({phones*100//total if total > 0 else 0}%)")
        print(f"Addresses: {addresses} ({addresses*100//total if total > 0 else 0}%)")
        print(f"Key People: {key_people} ({key_people*100//total if total > 0 else 0}%)")
        print(f"Key Person Emails: {key_emails} ({key_emails*100//total if total > 0 else 0}%)")
        print(f"{'='*60}\n")

    async def cleanup(self):
        """Clean up resources"""
        try:
            if self.selenium_driver:
                self.selenium_driver.quit()
        except:
            pass
        
        try:
            if self.browser:
                await self.browser.close()
            if self.playwright:
                await self.playwright.stop()
        except:
            pass

async def main():
    print("\n" + "="*60)
    print("🚀 GOODFIRMS HYBRID SCRAPER v5.1 (TIMEOUT FIXED)")
    print("="*60)
    print("\n✨ ARCHITECTURE:")
    print("   • GoodFirms → Selenium (HEADED, 1 browser)")
    print("   • Websites → Playwright (HEADLESS, parallel contexts)")
    print("   • 5-10x faster than traditional scraping!")
    print("   • ⏱ Comprehensive timeouts to prevent hanging")
    print("\nExtracts: Website, Email, Phone, Address, Key Person + Title\n")
    
    # Get start page
    while True:
        try:
            start_page = input("Enter START page number (1-100): ").strip()
            if not start_page:
                print("❌ Please enter a number!\n")
                continue
            start_page = int(start_page)
            if start_page < 1 or start_page > 100:
                print("❌ Enter between 1-100!\n")
                continue
            break
        except ValueError:
            print("❌ Invalid number!\n")
        except KeyboardInterrupt:
            print("\n\n👋 Cancelled!")
            exit(0)
    
    # Get end page
    while True:
        try:
            end_page = input(f"Enter END page number ({start_page}-100): ").strip()
            if not end_page:
                print("❌ Please enter a number!\n")
                continue
            end_page = int(end_page)
            if end_page < start_page or end_page > 100:
                print(f"❌ Enter between {start_page}-100!\n")
                continue
            total_pages = end_page - start_page + 1
            est_companies = total_pages * 15
            print(f"\n✓ Will scrape ~{est_companies} companies from pages {start_page} to {end_page}\n")
            break
        except ValueError:
            print("❌ Invalid number!\n")
        except KeyboardInterrupt:
            print("\n\n👋 Cancelled!")
            exit(0)
    
    # Get number of parallel workers
    while True:
        try:
            workers_input = input("Number of parallel workers (3-10) [5]: ").strip()
            if workers_input == '':
                max_workers = 5
                print(f"✓ Using 5 parallel workers\n")
                break
            max_workers = int(workers_input)
            if max_workers < 3 or max_workers > 10:
                print("❌ Enter between 3-10!\n")
                continue
            print(f"✓ Using {max_workers} parallel workers\n")
            break
        except ValueError:
            print("❌ Invalid number!\n")
        except KeyboardInterrupt:
            print("\n\n👋 Cancelled!")
            exit(0)
    
    print("="*60)
    print("CONFIGURATION SUMMARY:")
    print(f"   • GoodFirms: Selenium (HEADED)")
    print(f"   • Websites: Playwright (HEADLESS)")
    print(f"   • Parallel workers: {max_workers}")
    print(f"   • Pages: {start_page} to {end_page}")
    print(f"   • Timeouts: Enabled (prevents hanging)")
    print("="*60 + "\n")
    
    scraper = HybridScraper(max_workers=max_workers)
    
    try:
        await scraper.run(start_page, end_page)
    except KeyboardInterrupt:
        print("\n\n⚠ Interrupted by user")
        scraper.save_results(f"GoodFirms_Interrupted_Pages_{start_page}_to_{end_page}.xlsx")
    except Exception as e:
        print(f"\n\n✗ Error: {e}")
        traceback.print_exc()
        scraper.save_results(f"GoodFirms_Error_Recovery_Pages_{start_page}_to_{end_page}.xlsx")
    finally:
        await scraper.cleanup()
    
    print("\n✓ Done!")


def scrape_goodfirm(keyword, location, max_results=20):
    """Run the GoodFirm hybrid scraper and normalize leads for the backend."""
    pages = max(1, min(3, (max_results + 14) // 15))
    scraper = HybridScraper(max_workers=3)

    try:
        asyncio.run(scraper.run(1, pages))
    except Exception as exc:
        raise RuntimeError(f"GoodFirm scraper failed: {exc}")

    def normalize_value(value):
        if value is None:
            return None
        text = str(value).strip()
        if not text or text.lower() == 'not available':
            return None
        return text

    normalized = []
    for item in scraper.results[:max_results]:
        normalized.append({
            'business_name': normalize_value(item.get('Company Name') or item.get('name')) or 'Unknown',
            'phone': normalize_value(item.get('Phone')),
            'address': normalize_value(item.get('Address')),
            'website': normalize_value(item.get('Website')),
            'email': normalize_value(item.get('Email')),
            'source': 'goodfirm',
            'data': item,
        })

    return normalized


if __name__ == "__main__":
    # Install Playwright if needed
    print("\n💡 Make sure you have installed Playwright:")
    print("   pip install playwright")
    print("   playwright install chromium\n")
    
    asyncio.run(main())