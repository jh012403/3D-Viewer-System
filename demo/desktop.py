"""Windows primary-monitor metrics, without changing display settings."""
import ctypes

def monitor():
    user=ctypes.windll.user32
    user.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    width,height=user.GetSystemMetrics(0),user.GetSystemMetrics(1)
    user.GetDpiForSystem.restype=ctypes.c_uint
    dpi=user.GetDpiForSystem()
    return {'width':width,'height':height,'scale':dpi/96,'dpi':dpi,
            'css_width':round(width/(dpi/96)),'css_height':round(height/(dpi/96))}

if __name__=='__main__':
    print(monitor())
