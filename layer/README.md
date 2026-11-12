# reportlab Lambda layer

`generate_pdf` and `scheduled_pdf` import `reportlab`, which is not in the Lambda Python runtime. It is published once as a layer and attached to both functions.

Lambda runs on Linux, so the wheels must be Linux builds even when you package on Windows or macOS. A plain `pip install` on Windows produces a layer that fails at import time with `cannot import name '_imaging' from 'PIL'`.

```bash
pip install -r requirements.txt \
  --platform manylinux2014_x86_64 --implementation cp --python-version 3.12 \
  --only-binary=:all: --target python

zip -r reportlab-layer.zip python
aws lambda publish-layer-version --layer-name oms-reportlab \
  --zip-file fileb://reportlab-layer.zip --compatible-runtimes python3.12
```
