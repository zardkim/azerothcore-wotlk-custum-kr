# -*- coding: utf-8 -*-
"""빌드 스크립트(build.bat)가 매 빌드마다 실행: version.py 의 patch 번호를 자동으로
올리고, 그 버전을 담은 version_info.txt(exe 버전 리소스용)를 새로 생성한다.
v0.1.0 부터 시작해서 빌드할 때마다 0.1.1, 0.1.2, ... 로 올라간다."""
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
VERSION_PY = os.path.join(HERE, "version.py")
VERSION_INFO_TXT = os.path.join(HERE, "version_info.txt")


def read_version():
    with open(VERSION_PY, "r", encoding="utf-8") as f:
        content = f.read()
    m = re.search(r'__version__\s*=\s*"(\d+)\.(\d+)\.(\d+)"', content)
    if not m:
        return (0, 1, 0)
    return tuple(int(x) for x in m.groups())


def write_version(major, minor, patch):
    with open(VERSION_PY, "w", encoding="utf-8") as f:
        f.write(
            '# -*- coding: utf-8 -*-\n'
            '"""현재 런처 버전 — build.bat 이 빌드할 때마다 patch 번호를 자동으로 올려서 '
            '이 파일을 다시 씁니다."""\n'
            f'__version__ = "{major}.{minor}.{patch}"\n'
        )


def write_version_info(major, minor, patch):
    ver_tuple = f"({major}, {minor}, {patch}, 0)"
    ver_str = f"{major}.{minor}.{patch}.0"
    content = f"""VSVersionInfo(
  ffi=FixedFileInfo(
    filevers={ver_tuple},
    prodvers={ver_tuple},
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo(
      [
      StringTable(
        u'040904B0',
        [StringStruct(u'CompanyName', u'zardkim'),
        StringStruct(u'FileDescription', u'WOW Launcher - WOW Legends server launcher'),
        StringStruct(u'FileVersion', u'{ver_str}'),
        StringStruct(u'InternalName', u'WOW Launcher'),
        StringStruct(u'LegalCopyright', u'\\xa9 zardkim'),
        StringStruct(u'OriginalFilename', u'WOW Launcher.exe'),
        StringStruct(u'ProductName', u'WOW Launcher'),
        StringStruct(u'ProductVersion', u'{ver_str}')])
      ]),
    VarFileInfo([VarStruct(u'Translation', [1033, 1200])])
  ]
)
"""
    with open(VERSION_INFO_TXT, "w", encoding="utf-8") as f:
        f.write(content)


def main():
    major, minor, patch = read_version()
    patch += 1
    write_version(major, minor, patch)
    write_version_info(major, minor, patch)
    print(f"{major}.{minor}.{patch}")


if __name__ == "__main__":
    main()
