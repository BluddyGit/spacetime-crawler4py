from bs4 import BeautifulSoup

import re
from urllib.parse import urlparse, urljoin, urldefrag

def scraper(url, resp):
    links = extract_next_links(url, resp)
    return [link for link in links if is_valid(link)]

unique_pages = set()
word_count = {}
longest_page = {"url" : "", "count" : 0}
subdomains = {}

# Implementation required.
def extract_next_links(url, resp):

    # resp.status: the status code returned by the server. 200 is OK, you got the page. Other numbers mean that there was some kind of problem.
    if resp.status != 200:
        return []

    # resp.raw_response: this is where the page actually is. More specifically, the raw_response has two parts:
    #         resp.raw_response.url: the url, again
    #         resp.raw_response.content: the content of the page!
    soup = BeautifulSoup(resp.raw_response.content, "lxml")

    urls = []

    # url: the URL that was used to get the page
    unique_pages.add(urldefrag(url).url)
    for tag in soup.find_all("a"):
        href = tag.get("href")
        if href is None:
            continue
        
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

    if len(tokens_not_numeric) > longest_page["count"]:
        longest_page["url"] = url
        longest_page["count"] = len(tokens_not_numeric)

    for token in tokens_not_numeric:
        word_count[token] = word_count.get(token, 0) + 1

    parsed = urlparse(url)
    netloc = parsed.netloc
    if netloc not in subdomains:
        subdomains[netloc] = set()
    subdomains[netloc].add(url)

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
