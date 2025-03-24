import re
import requests
from m3u8 import M3U8
from m3u8download import download_m3u8_video_with_progressbar


def get_video_urls(baseUrl):
    resp = requests.get(baseUrl, headers={'User-Agent': 'Mozilla/5.0'})
    resp.encoding = resp.apparent_encoding
    html = resp.text
    name = re.findall(r"<h3>(.*?)</h3>", html)[0]
    # //相关报导
    # var jsonData=[];
    # //粗切 正片
    # var jsonData1=[];
    # //精切 花絮
    # var jsonData2=[];
    # json_data = re.findall(r'var jsonData2=(.*?)</script>', html, re.S)[0] # 个别情况正片在花絮，如侠岚全集
    json_data = re.findall(r"var jsonData1=(.*?)</script>", html, re.S)[0]  # 侠岚高清
    titles = re.findall(r"""['"]title['"]:['"](.*?)['"]""", json_data)
    urls = re.findall(r"""['"]url['"]:['"](.*?)['"]""", json_data)
    # print(name, titles, urls)
    return name, zip(titles, urls)


def handle_page(title, url):
    resp = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
    resp.encoding = resp.apparent_encoding
    html = resp.text
    pid = re.findall(r'var guid = "(.*?)"', html)[0]
    url = 'https://vdn.apps.cntv.cn/api/getHttpVideoInfo.do?pid=' + pid
    resp = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
    data = resp.json()
    hls_url = data['hls_url']
    return title, hls_url


def get_recursive_m3u8_url(m3u8_url):
    resp = requests.get(m3u8_url, headers={'User-Agent': 'Mozilla/5.0'})
    resp.encoding = resp.apparent_encoding
    m3u8 = M3U8(resp.text)
    while m3u8.is_variant:
        base_uri = "https://hls.cntv.lxdns.com"
        playlist = m3u8.playlists[0]
        m3u8_url = base_uri + playlist.uri
        resp = requests.get(m3u8_url, headers={'User-Agent': 'Mozilla/5.0'})
        resp.encoding = resp.apparent_encoding
        m3u8 = M3U8(resp.text)
    return m3u8_url


if __name__ == '__main__':
    # baseUrl = "https://tv.cctv.com/2013/01/31/VIDA1359627240942487.shtml"   # 侠岚全集
    baseUrl = "https://donghua.cctv.com/2013/04/15/VIDA1366020360689583.shtml"   # 侠岚高清
    name, video_urls = get_video_urls(baseUrl)
    for title, url in video_urls:
        title, hls_url = handle_page(title, url)
        m33u8_url = get_recursive_m3u8_url(hls_url)
        print(f"Downloading {name}/{title}...")
        download_m3u8_video_with_progressbar(m33u8_url, title, output_dir=name, exist_ok=True)
