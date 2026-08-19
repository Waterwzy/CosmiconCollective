## 本项目已停止更新

由于效果偏离了既定目标并且尚无有效的解决方法，本项目停止更新，但你依旧可以使用本项目。

## QuickStart

```bash
git clone git@github.com:Waterwzy/CosmiconCollective.git
cd CosmiconCollective
python -m venv .venv
```

Windows系统：

```bash
.venv/Scripts/Activate.ps1
```

Linux/MacOS：

```bash
.venv/bin/activate
```

需要填写 `.env` 环境变量以启动项目，`.evn.example` 为填写示例，这里不再赘述。

安装依赖并启动项目：

```bash
pip install -e .
python -m webui
```

项目会在端口 `8000` 上运行。