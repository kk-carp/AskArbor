# 虚构 FDE 课程代码样例（V2-A1）

本目录仅用于课程代码入库演示，不是真实内部仓。

打包示例（在本目录执行）：

```powershell
Compress-Archive -Path labs,notes,README.md -DestinationPath course_code.zip
```

或在仓库根目录用 Python：

```powershell
python -c "from pathlib import Path; from zipfile import ZipFile; root=Path('docs/samples/v2a'); zip_path=root/'course_code.zip';
import os
with ZipFile(zip_path,'w') as z:
    for p in root.rglob('*'):
        if p.is_file() and p.name!='course_code.zip' and p.name!='README.md':
            z.write(p, p.relative_to(root).as_posix())
print(zip_path)"
```

教学岗登录后：

```powershell
curl.exe -c cookies.txt -b cookies.txt -X POST "http://127.0.0.1:8000/code-ingest" -F "file=@docs/samples/v2a/course_code.zip"
```

空间由服务端定为 `student`，客户端传 `space` 无效。
