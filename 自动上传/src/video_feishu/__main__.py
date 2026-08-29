import traceback
from pathlib import Path
import tempfile

try:
    from video_feishu.startup import cleanup_old_versions
    cleanup_old_versions()
    from video_feishu.app import main
    main()
except Exception:
    Path(tempfile.gettempdir(), "VideoFeishuTool-startup-error.txt").write_text(traceback.format_exc(), "utf-8")
    raise
