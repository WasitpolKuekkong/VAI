from config.settings import load_settings

c = load_settings()
print('rvc_model_pth=', c.rvc_model_pth)
print('rvc_model_index=', c.rvc_model_index)
print('pth exists=', c.rvc_model_pth.exists())
print('index exists=', c.rvc_model_index.exists())
