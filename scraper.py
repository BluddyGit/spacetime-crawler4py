from bs4 import BeautifulSoup

import re
from urllib.parse import urlparse, urljoin, urldefrag
import atexit

def scraper(url, resp):
    links = extract_next_links(url, resp)
    return [link for link in links if is_valid(link)]

unique_pages = set()
word_count = {}
longest_page = {"url" : "", "count" : 0}
subdomains = {}

STOP_WORDS = set([
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and", 
    "any", "are", "aren", "as", "at", "be", "because", "been", "before", "being", 
    "below", "between", "both", "but", "by", "can", "cannot", "could", "couldn", 
    "did", "didn", "do", "does", "doesn", "doing", "don", "down", "during", "each", 
    "few", "for", "from", "further", "had", "hadn", "has", "hasn", "have", "haven", 
    "having", "he", "her", "here", "hers", "herself", "him", "himself", "his", "how", 
    "i", "if", "in", "into", "is", "isn", "it", "its", "itself", "let", "me", "more", 
    "most", "mustn", "my", "myself", "no", "nor", "not", "of", "off", "on", "once", 
    "only", "or", "other", "ought", "our", "ours", "ourselves", "out", "over", "own", 
    "same", "shan", "she", "should", "shouldn", "so", "some", "such", "than", "that", 
    "the", "their", "theirs", "them", "themselves", "then", "there", "these", "they", 
    "this", "those", "through", "to", "too", "under", "until", "up", "very", "was", 
    "wasn", "we", "were", "weren", "what", "when", "where", "which", "while", "who", 
    "whom", "why", "will", "with", "won", "would", "wouldn", "you", "your", "yours", 
    "yourself", "yourselves"
])

# Implementation required.
def extract_next_links(url, resp):

    # resp.status: the status code returned by the server. 200 is OK, you got the page. Other numbers mean that there was some kind of problem.
    if resp.status != 200:
        return []

    if not resp.raw_response or not resp.raw_response.content:
        return []

    if len(resp.raw_response.content) > 5 * 1024 *1024:
        return []
    
    # if it's PDF, image, or random binary data, ignore it
    content_type = resp.raw_response.headers.get("content-type", "")
    if not content_type.startswith("text/html"):
        return []
    
    # resp.raw_response: this is where the page actually is. More specifically, the raw_response has two parts:
    #         resp.raw_response.url: the url, again
    #         resp.raw_response.content: the content of the page!
    soup = BeautifulSoup(resp.raw_response.content, "lxml")

    # Prevent processing the exact duplicate pages
    defragged_url = urldefrag(url).url
    if defragged_url in unique_pages:
        return []
    unique_pages.add(defragged_url)

    urls = []
    for tag in soup.find_all("a"):
        href = tag.get("href")
        if href:
            new_url = urldefrag(urljoin(url, href)).url
            urls.append(new_url)

    for tag in soup(["script", "style"]):
        tag.decompose()

    text = soup.get_text(separator=" ")
    
    tokens = re.split(r"\W+", text.lower())
    tokens_list = [t for t in tokens if t]
    tokens_not_urls = [t for t in tokens_list if not any(t.startswith(word) for word in ["http", "https", "www", "uci", "edu", "html", "htm"])]
    tokens_min = [t for t in tokens_not_urls if len(t) > 1]
    tokens_not_numeric = [t for t in tokens_min if not t.isnumeric()]
    valid_tokens = [t for t in tokens_not_numeric if t not in STOP_WORDS]

    if len(valid_tokens) < 50:
        return []

    if len(valid_tokens) > longest_page["count"]:
        longest_page["url"] = url
        longest_page["count"] = len(valid_tokens)

    for token in valid_tokens:
        word_count[token] = word_count.get(token, 0) + 1

    parsed = urlparse(defragged_url)
    netloc = parsed.netloc

    if any(netloc.endswith(domain) for domain in [".ics.uci.edu", ".cs.uci.edu", ".informatics.uci.edu", ".stat.uci.edu"]) or netloc in ["ics.uci.edu", "cs.uci.edu", "informatics.uci.edu", "stat.uci.edu"]:
        if netloc not in subdomains:
            subdomains[netloc] = set()
        subdomains[netloc].add(defragged_url)

    # Return a list with the hyperlinks (as strings) scrapped from resp.raw_response.content
    return urls

def is_valid(url):
    # Decide whether to crawl this url or not. 
    # If you decide to crawl it, return True; otherwise return False.
    # There are already some conditions that return False.
    try:
        parsed = urlparse(url)
        if parsed.scheme not in set(["http", "https"]):
            return False
        if not any(parsed.netloc.endswith(domain) for domain in [".ics.uci.edu", ".cs.uci.edu", ".informatics.uci.edu", ".stat.uci.edu"]):
            return False

        # Trap: Long URLs
        if len(url) > 200:
            return False
        
        # Trap: Too many query parameters (e.g ?a=1&b=2&c=3&d=4...)
        if url.count('?') > 0 and url.count('&') > 3:
            return False
        
        # Trap: Repeating directories in path
        if re.match(r"^.*?(/.+?/).*?\1.*$|^.*?/(.+?/)\2.*$", parsed.path):
            return False

        # Trap: Calendar/Date Formats (Catches /2024/09 or /2024-09)
        if re.search(r"/(19|20)\d{2}[-/]\d{2}", parsed.path.lower()):
            return False

        # Trap: Too many query parameters (e.g ?a=1&b=2&c=3...)
        if url.count('?') > 0 and url.count('&') > 3:
            return False
        
        # Trap: DokuWiki infinite index and action
        if "doku.php" in parsed.path.lower():
            return False
        
        # Trap: Dokuwiki excessively deep namespaces (saw a lot of this in your log)
        if parsed.path.count(':') > 2:
            return False
        
        # Trap: WICS / School quarters infinite future loops (e.g., winter-2026-week-8)
        if re.search(r"/(fall|winter|spring|summer)-\d{4}", parsed.path.lower()):
            return False
        
        trap_params = ['skin=', 'lang=', 'action=', 'replytocom=', 'share=', 'version=', 'do=export', 'jmepopupweb=']
        if any(param in parsed.query.lower() for param in trap_params):
            return False
        
        # Trap: Infinite Calendars and iCal exports
        if "ical=" in parsed.query.lower():
            return False
        
        # Trap: Event Calendar paths 
        if "/events/" in parsed.path.lower() or "/event/" in parsed.path.lower():
            return False

        # Trap: Blog and News pagination loops
        if "/page/" in parsed.path.lower():
            return False
            
        # Trap: Apache directory sorting parameters (e.g., ?C=N;O=D)
        # This catches anything trying to sort by Name, Date, Size, etc.
        if "c=" in parsed.query.lower() and "o=" in parsed.query.lower():
            return False
            
        # Trap: Dynamic search pages and filters
        if "search=" in parsed.query.lower() or "keywords=" in parsed.query.lower():
            return False

        # Trap: Common raw data and code directories in faculty/student spaces
        if "/~" in parsed.path.lower() and re.search(r'/(?:code|src|data|dataset|datasets|bin|patch|releases)/', parsed.path.lower()):
            return False
        
        # Trap: Faculty publication, papers, and citation directories
        # Matches paths like /pub/, /pubs/, /papers/, or files like publications.html
        if re.search(r'/(?:pub|pubs|publications|papers|research-papers|presentations)(?:/|\.html?$)', parsed.path.lower()):
            return False
        if re.search(r'/(?:sld|slide)\d+\.html?$', parsed.path.lower()):
            return False
        
        if "dale-cooper" in parsed.netloc.lower():
            return False
        if "mailman" in parsed.netloc or "/mailman/" in parsed.path.lower():
            return False
        if "wp-login.php" in parsed.path.lower() or "wp-admin" in parsed.path.lower():
            return False
        
        # Trap: Dynamic time-based server dashboards (Grafana)
        if "grafana" in parsed.netloc.lower() or "from=" in parsed.query.lower():
            return False
        
        # Trap: Helpdesk tickets and Request Tracker databases
        if re.search(r'/(ticket|requesttracker|dtr)/', parsed.path.lower()):
            return False
        
        # Trap: Block login, registration, and password reset pages
        if re.search(r'/(auth|login|register|password_reset|contribute)', parsed.path.lower()):
            return False

        # Trap: Raw WordPress post and page IDs (e.g., ?p=123 or ?page_id=123)
        if re.match(r'^p=\d+', parsed.query.lower()) or re.match(r'^page_id=\d+', parsed.query.lower()):
            return False
            
        # Trap: WordPress editor artifacts/glitches
        if "_wp_link_placeholder" in parsed.path.lower():
            return False
            
        # Trap: Block the beta test site so we don't crawl duplicates
        if "archive-beta.ics.uci.edu" in parsed.netloc.lower():
            return False
            
        # Trap: Block the dynamic sorting queries on the ML archive
        if "order=" in parsed.query.lower():
            return False
        
        return not re.match(
            r".*\.(css|js|bmp|gif|jpe?g|ico"
            + r"|png|tiff?|mid|mp2|mp3|mp4"
            + r"|wav|avi|mov|mpeg|ram|m4v|mkv|ogg|ogv|pdf"
            + r"|ps|eps|tex|ppt|pptx|doc|docx|xls|xlsx|names"
            + r"|data|dat|exe|bz2|tar|msi|bin|7z|psd|dmg|iso"
            + r"|epub|dll|cnf|tgz|sha1"
            + r"|thmx|mso|arff|rtf|jar|csv"
            + r"|rm|smil|wmv|swf|wma|zip|rar|gz)$", parsed.path.lower())

    except TypeError:
        print ("TypeError for ", parsed)
        raise


def generate_report():
    print("\n" + "="*60)
    print("                 CRAWLER REPORT")
    print("="*60)

    # 1. Unique pages
    print(f"\n1. Total unique pages found: {len(unique_pages)}")

    # 2. Longest page
    print(f"\n2. Longest page in terms of words:")
    print(f"   URL: {longest_page['url']}")
    print(f"   Word Count: {longest_page['count']}")

    # 3. 50 Most Common Words (ignoring stop words)
    print("\n3. Top 50 most common words:")
    sorted_words = sorted(word_count.items(), key=lambda x: x[1], reverse=True)[:50]
    for rank, (word, count) in enumerate(sorted_words, 1):
        print(f"   {rank}. {word}: {count}")

    # 4. Subdomains
    print("\n4. Subdomains in target domains:")
    for sub in sorted(subdomains.keys()):
        print(f"   {sub}, {len(subdomains[sub])}")
    
    print("="*60 + "\n")

# This tells Python to automatically run the function above when the crawler finishes OR when you press Ctrl+C
atexit.register(generate_report)