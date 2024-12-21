# 邮件群发工具 Pro

一个功能强大的邮件群发工具，支持多代理轮换、多发件箱轮询、智能速率控制等特性。

## 核心功能
### 1. 智能发送控制
- 多发件箱轮询发送
- 智能速率自适应调节
- 发送状态实时监控
- 支持断点续发功能

## 代理管理
- 多代理自动轮换
- 并发代理可用性检测
- 智能故障切换机制
- 实时显示代理出口IP

## 邮箱验证
- 严格的格式校验
- 智能域名检测
- 自动过滤无效地址
- 分类记录无效原因

## 数据处理
- 自动更新邮箱列表
- 成功发送记录追踪
- 失败原因分类存储
- JSON格式状态保存

## 系统要求
- Python 3.8+
- 支持 Windows/Linux/MacOS
- 稳定的网络连接
- SMTP服务器支持

## 快速开始
1. 安装依赖
```bash
pip3 install -r requirements.txt
```

2. 配置文件
```toml
# config.toml
[smtp]
host = "smtp服务器地址"
port = 465
from_list = [
    { name = "显示名称", email = "发件邮箱" }
]

[smtp.passwords]
"发件邮箱" = "邮箱密码"

[setting]
limit = 30  # 每分钟发送量
```

3. 准备文件
- `emails.txt`: 收件人列表，每行一个邮箱
- `email.html`: 邮件内容模板(HTML格式)

4. 运行程序
```bash
python3 main.py
```

## 文件说明
- `config.toml`: 配置文件，包含SMTP设置、代理列表等
- `emails.txt`: 收件人邮箱列表，每行一个
- `email.html`: 邮件内容模板（HTML格式）
- `success_emails.txt`: 发送成功的邮箱记录
- `failed_emails.txt`: 发送失败的邮箱记录
- `invalid_emails.txt`: 格式无效的邮箱记录
- `mail_sender.log`: 运行日志
- `sender_state.json`: 发送状态文件

## 初始配置
1. 复制 `config.example.toml` 为 `config.toml`
2. 在 `config.toml` 中配置：
    - SMTP服务器信息
    - 发件邮箱及密码
    - 发送速率限制
    - 代理服务器信息（可选）

## 邮箱支持
默认支持的邮箱域名：
- Gmail (@gmail.com)
- Outlook (@outlook.com)
- Yahoo (@yahoo.com)
- Hotmail (@hotmail.com)

可在 `main.py` 中的 `COMMON_EMAIL_DOMAINS` 添加更多支持的域名。

## 代理配置
支持的代理格式：
```
server:port:username:password
```

例如：
```
proxy.example.com:8080:user123:pass456
```

## 错误处理
- 发送失败的邮箱会记录到 `failed_emails.txt`
- 无效的邮箱格式会记录到 `invalid_emails.txt`
- 详细的错误日志保存在 `mail_sender.log`

## 断点续发
- 程序会自动保存发送进度
- 中断后重启会从上次位置继续
- 发送状态保存在 `sender_state.json`

## 高级特性
- 智能速率控制：自动调整发送速率，避免服务器拦截
- 多代理轮换：支持HTTP/SOCKS5代理，自动故障转移
- 状态保存：支持中断恢复，自动保存发送进度
- 实时监控：详细的日志记录和统计报告

## 注意事项
1. 确保SMTP服务器支持SSL连接
2. 代理服务器需支持HTTPS协议
3. 建议先小批量测试
4. 定期检查发送日志
5. 不要在公共环境保存敏感信息
6. 建议使用专用的发信邮箱
7. 遵守相关法律法规

## 常见问题
1. SMTP认证失败
    - 检查邮箱密码是否正确
    - 确认是否启用了SMTP服务
    - 某些邮箱需要生成应用专用密码

2. 代理连接失败
    - 验证代理服务器是否在线
    - 检查代理账号密码是否正确
    - 确认代理支持HTTPS协议

3. 发送速率问题
    - 初始建议设置较低的速率
    - 观察成功率来调整发送速度
    - 不同SMTP服务器限制不同

## Telegram
@enyccd

## 开源协议

MIT License

Copyright (c) 2024 kidcc

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
