# -*- coding: utf-8 -*-
"""클라이언트 다운로드(7-Zip SFX 자동압축풀림 exe 하나만 지원) + 설치.

배포 파일은 반드시 "설치형(;!@Install@!UTF-8! 구성 블록)"이 아닌 "단순 압축 풀기"
SFX 모듈(7z.sfx 또는 7zCon.sfx)로 만든 self-extracting 7z여야 한다. 그래야
`-y -o<폴더>` 같은 표준 7-Zip 명령줄 스위치가 그대로 먹혀서, 이 런처가 대화상자
없이 조용히 지정 폴더에 풀 수 있다. 설치형 SFX(콘요 구성 블록이 들어간 것)로
만들면 이 스위치들이 무시되고 내부에 미리 정해둔 동작만 실행되므로 쓰면 안 된다.

  copy /b 7z.sfx + archive.7z client.exe

식으로 만든 파일을 다운로드 URL에 올려두면 된다(7-Zip 설치 폴더 안의 7z.sfx 사용).
"""
import os
import subprocess
import urllib.request
import urllib.error

CHUNK_SIZE = 256 * 1024


class DownloadError(Exception):
    pass


def _parse_content_range_total(content_range):
    """'bytes 1000-1999/5000' 형식 Content-Range 헤더에서 전체 크기(5000)만 뽑는다.
    형식이 예상과 다르면(서버가 '*'로 total을 안 주는 등) None."""
    if not content_range:
        return None
    try:
        return int(content_range.rsplit("/", 1)[1])
    except (IndexError, ValueError):
        return None


def download_file(url, dest_path, progress_cb=None, timeout=30):
    """progress_cb(downloaded_bytes, total_bytes)를 진행 중 계속 호출한다
    (total_bytes는 서버가 크기를 안 주면 0).

    이어받기: dest_path + ".part" 파일이 이미 있으면(이전 시도가 중간에 끊긴 경우)
    그 크기만큼 Range 헤더로 이어받기를 시도한다. 서버가 Range를 지원하지 않으면
    (206 Partial Content가 아니면) 처음부터 다시 받는다. 클라이언트 설치 파일은
    용량이 커서(수 GB) 매번 처음부터 다시 받게 하면 안 되므로, 네트워크 오류로
    실패하더라도 지금까지 받은 .part는 지우지 않고 남겨둔다 — 다음 시도가 이어서
    받을 수 있게. 서버가 이어받기 위치를 인식 못 하는 경우(416)에만 .part를 지우고
    새로 시작한다."""
    tmp_path = dest_path + ".part"
    resume_from = os.path.getsize(tmp_path) if os.path.isfile(tmp_path) else 0

    headers = {"User-Agent": "WOWLegendsPlayerLauncher/1.0"}
    if resume_from:
        headers["Range"] = f"bytes={resume_from}-"
    req = urllib.request.Request(url, headers=headers)

    try:
        resp = urllib.request.urlopen(req, timeout=timeout)
    except urllib.error.HTTPError as e:
        if e.code == 416 and resume_from:
            try:
                os.remove(tmp_path)
            except OSError:
                pass
            return download_file(url, dest_path, progress_cb=progress_cb, timeout=timeout)
        raise DownloadError(f"다운로드 실패: {e}") from e
    except (urllib.error.URLError, OSError, TimeoutError) as e:
        raise DownloadError(f"다운로드 실패: {e}") from e

    try:
        status = getattr(resp, "status", None) or resp.getcode()
        if resume_from and status == 206:
            total = _parse_content_range_total(resp.headers.get("Content-Range")) or 0
            mode, downloaded = "ab", resume_from
        else:
            # 서버가 이어받기를 지원하지 않으면(200으로 전체를 다시 보냄) 처음부터
            # 새로 받는다 - 기존 .part 뒤에 이어붙이면 파일이 깨진다.
            total = int(resp.headers.get("Content-Length", 0) or 0)
            mode, downloaded = "wb", 0
        try:
            with open(tmp_path, mode) as f:
                while True:
                    chunk = resp.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    if progress_cb:
                        progress_cb(downloaded, total)
        except (OSError, TimeoutError) as e:
            raise DownloadError(f"다운로드 실패: {e}") from e
    finally:
        resp.close()

    os.replace(tmp_path, dest_path)


def extract_7z_sfx(sfx_path, dest_dir, timeout=1800):
    """단순 압축 풀기용 7-Zip SFX exe를 조용히(대화상자 없이) dest_dir에 푼다.
    성공 시 True, 실패 시 (False, 표준에러 텍스트)를 돌려준다."""
    os.makedirs(dest_dir, exist_ok=True)
    try:
        result = subprocess.run(
            [sfx_path, "-y", f"-o{dest_dir}"],
            timeout=timeout,
            capture_output=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
    except (OSError, subprocess.SubprocessError) as e:
        return False, str(e)
    if result.returncode == 0:
        return True, ""
    stderr = (result.stderr or b"").decode("utf-8", errors="replace").strip()
    return False, stderr or f"압축 풀기 실패 (종료 코드 {result.returncode})"
