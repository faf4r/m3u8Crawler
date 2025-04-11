import os
import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from m3u8 import M3U8
from Crypto.Cipher import AES  # 需要安装pycryptodome
from tqdm import tqdm


def download_m3u8_video(m3u8_index_url, filename="output", output_dir=".", exist_ok=False):
    """
    无嵌套(m3u8.is_variant=False)的m3u8视频下载
    :param url: m3u8文件的URL
    :param filename: 输出文件名
    :param output_dir: 输出目录
    :param exist_ok: 如果文件已存在是否跳过下载
    """
    # 创建临时目录
    temp_dir = f"ts_temp/{filename}"
    os.makedirs(temp_dir, exist_ok=True)
    os.makedirs(output_dir, exist_ok=True)
    if exist_ok and os.path.exists(f"{output_dir}/{filename}.ts"):
        print(f"🎉 {output_dir}/{filename}.ts 已存在，跳过下载！")
        return

    # 1. 下载并解析m3u8文件
    session = requests.Session()
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Referer": m3u8_index_url.rsplit("/", 1)[0] + "/",
    }

    base_uri = m3u8_index_url.rsplit("/", 1)[0] + "/"
    m3u8_content = session.get(m3u8_index_url, headers=headers).text
    playlist = M3U8(m3u8_content)

    # 2. 处理加密（如果有）
    key = None
    if playlist.keys and playlist.keys[0]:
        key_uri = playlist.keys[0].uri
        key_uri = key_uri if key_uri.startswith("http") else base_uri + key_uri
        key_response = session.get(key_uri, headers=headers)
        key = key_response.content

    # 3. 下载所有ts片段
    def download_ts(segment, index):
        print(f"Downloading {temp_dir}/{index:05d}.ts")
        ts_url = segment.uri if segment.uri.startswith("http") else base_uri + segment.uri
        response = session.get(ts_url, headers=headers)

        # 处理解密
        if key and segment.key:
            if segment.key.iv:
                iv = bytes.fromhex(segment.key.iv[2:]) # str to bytes
            else:
                iv = key
            cipher = AES.new(key, AES.MODE_CBC, iv=iv)
            content = cipher.decrypt(response.content)
        else:
            content = response.content

        with open(f"{temp_dir}/{index:05d}.ts", "wb") as f:
            f.write(content)

    with ThreadPoolExecutor(max_workers=os.cpu_count()) as executor:
        futures = [
            executor.submit(download_ts, seg, idx)
            for idx, seg in enumerate(playlist.segments)
        ]
        for future in as_completed(futures):
            future.result()
    # for idx, seg in enumerate(playlist.segments):
    #     download_ts(seg, idx)

    # 4. 合并ts文件
    with open(f"{output_dir}/{filename}.ts", "wb") as merged:
        for ts_file in sorted(os.listdir(temp_dir)):
            with open(f"{temp_dir}/{ts_file}", "rb") as f:
                merged.write(f.read())

    # 清理临时文件
    shutil.rmtree(temp_dir)
    # for f in os.listdir(temp_dir):
    #     os.remove(f"{temp_dir}/{f}")
    # os.rmdir(temp_dir)


def download_m3u8_video_with_progressbar(m3u8_index_url, filename="output", output_dir=".", exist_ok=False):
    """
    无嵌套(m3u8.is_variant=False)的m3u8视频下载
    :param url: m3u8文件的URL
    :param filename: 输出文件名
    :param output_dir: 输出目录
    :param exist_ok: 如果文件已存在是否跳过下载
    """
    # 创建临时目录
    temp_dir = f"ts_temp/{filename}"
    os.makedirs(temp_dir, exist_ok=True)
    os.makedirs(output_dir, exist_ok=True)
    if exist_ok and os.path.exists(f"{output_dir}/{filename}.ts"):
        print(f"🎉 {output_dir}/{filename}.ts 已存在，跳过下载！")
        shutil.rmtree(temp_dir)
        return

    # 1. 下载并解析m3u8文件
    session = requests.Session()
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Referer": m3u8_index_url.rsplit("/", 1)[0] + "/",
    }

    base_uri = m3u8_index_url.rsplit("/", 1)[0] + "/"
    m3u8_content = session.get(m3u8_index_url, headers=headers).text
    playlist = M3U8(m3u8_content)

    # 2. 处理加密（如果有）
    key = None
    if playlist.keys and playlist.keys[0]:
        key_uri = playlist.keys[0].uri
        key_uri = key_uri if key_uri.startswith("http") else base_uri + key_uri
        key_response = session.get(key_uri, headers=headers)
        key = key_response.content

    # 3. 下载所有ts片段
    total_segments = len(playlist.segments)
    progress_bar = tqdm(
        total=total_segments,
        desc="🚀 下载TS片段",
        unit="seg",
        bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]",
    )
    failed_segments = []
    def download_ts(segment, index):
        if os.path.exists(f"{temp_dir}/{index:05d}.ts"):
            progress_bar.update(1)
            return True
        ts_url = segment.uri if segment.uri.startswith("http") else base_uri + segment.uri
        try:
            response = session.get(ts_url, headers=headers)

            # 处理解密
            if key and segment.key:
                if segment.key.iv:
                    iv = bytes.fromhex(segment.key.iv[2:])  # str to bytes
                else:
                    iv = key
                cipher = AES.new(key, AES.MODE_CBC, iv=iv)
                content = cipher.decrypt(response.content)
            else:
                content = response.content

            with open(f"{temp_dir}/{index:05d}.ts", "wb") as f:
                f.write(content)

            # 更新进度条（线程安全）
            progress_bar.update(1)
            return True
        except Exception as e:
            progress_bar.write(f"⚠️ 片段 {index} 下载失败: {str(e)}")
            failed_segments.append((index, ts_url, segment))
            return False

    with ThreadPoolExecutor(max_workers=os.cpu_count()) as executor:
        futures = [
            executor.submit(download_ts, seg, idx)
            for idx, seg in enumerate(playlist.segments)
        ]
        # 等待任务完成（实时显示错误）
        for future in as_completed(futures):
            future.result()

    # 列出下载失败的片段自己手动下载后再次尝试合并
    if failed_segments:
        progress_bar.set_description("⚠️ 有下载失败的片段，请手动下载后再次尝试合并！")
        for idx, ts_url, segment in failed_segments:
            print(f"片段 {idx} URL: {ts_url}")
        return

    # 4. 合并ts文件
    progress_bar.set_description("🔧 合并文件中...")
    with open(f"{output_dir}/{filename}.ts", "wb") as merged:
        for ts_file in sorted(os.listdir(temp_dir)):
            with open(f"{temp_dir}/{ts_file}", "rb") as f:
                merged.write(f.read())

    # 清理临时文件
    progress_bar.set_description("🧹 清理临时文件...")
    shutil.rmtree(temp_dir)
    progress_bar.set_description("🎉 下载完成！")
    progress_bar.close()


# 使用示例
if __name__ == "__main__":
    # 《锦绣神州之姓氏王国》在B站缺失的部分
    # download_m3u8_video("https://v.gsuus.com/play/lej1J8zd/index.m3u8", "第2集《悠悠寸心》")
    # download_m3u8_video("https://v.gsuus.com/play/nel168Va/index.m3u8", "第3集《灵兽风波》")
    # download_m3u8_video_with_progressbar("https://v.gsuus.com/play/9b6QV9Qa/index.m3u8", "第4集《无姓灯笼》")
    # download_m3u8_video_with_progressbar("https://v.gsuus.com/play/pen1JYYd/index.m3u8", "第5集《试炼遇险》")
    download_m3u8_video_with_progressbar("https://v.gsuus.com/play/QeZ1X0Ed/index.m3u8", "第7集《扬帆起航》")
