"""打包入口：直接启动日报工作台 GUI。"""

import sys

from daily_report.gui.app import main

if __name__ == "__main__":
    sys.exit(main())
