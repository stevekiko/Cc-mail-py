import time
import smtplib
import random
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
from email import utils as email_utils
from tqdm import tqdm
import toml
import socks
import socket
import ssl
import requests
import os
import re
import logging
from concurrent.futures import ThreadPoolExecutor
import json

COMMON_EMAIL_DOMAINS = {
    # 国际主流
    'gmail.com', 'outlook.com', 'yahoo.com', 'hotmail.com',
    # 添加其他需要支持的域名
}

def reset_socket():
    """重置socket到默认状态"""
    if hasattr(socket, '_orig_socket'):
        socket.socket = socket._orig_socket
        time.sleep(1)  # 重置后等待

def test_proxy_connection(proxy, smtp_host, smtp_port):
    """测试代理连通性"""
    try:
        # 解析代理地址
        server, port, username, password = proxy.split(':')
        
        # 构建代理URL
        proxy_url = f"http://{username}:{password}@{server}:{port}"
        proxies = {
            'http': proxy_url,
            'https': proxy_url
        }
        
        # 测试代理连接
        try:
            response = requests.get('https://api.ipify.org?format=json', 
                                  proxies=proxies, 
                                  timeout=10,
                                  verify=False)
            if response.status_code == 200:
                real_ip = response.json()['ip']
                print(f"代理可用: {server}:{port}, 出口IP: {real_ip}")
                return True, 'http', real_ip
        except Exception as e:
            print(f"代理测试失败: {server}:{port}, 错误: {str(e)}")
            return False, None, None
            
    except Exception as e:
        print(f"代理格式错误: {str(e)}")
        return False, None, None

def create_smtp_handler(proxy=None, proxy_type=None):
    """创建SMTP处理器"""
    if proxy and proxy_type:
        try:
            # 解析代理地址
            proxy_server, proxy_port, proxy_username, proxy_password = proxy.split(':')
            
            # 创建代理处理的 SMTP_SSL 类
            class ProxySMTP_SSL(smtplib.SMTP_SSL):
                def _get_socket(self, host, port, timeout):
                    """创建代理socket"""
                    # 设置代理
                    socks.setdefaultproxy(
                        socks.PROXY_TYPE_HTTP,  # 直接使用 HTTP 代理
                        proxy_server,
                        int(proxy_port),
                        username=proxy_username,
                        password=proxy_password,
                        rdns=True
                    )
                    socks.wrapmodule(socket)
                    
                    # 创建socket连接
                    sock = socket.create_connection((host, port), timeout)
                    print(f"正在通过HTTP代理 {proxy_server}:{proxy_port} 连接到 {host}:{port}")
                    
                    # SSL包装
                    context = ssl.create_default_context()
                    context.check_hostname = False
                    context.verify_mode = ssl.CERT_NONE
                    ssl_sock = context.wrap_socket(sock, server_hostname=host)
                    return ssl_sock
                    
                def quit(self):
                    try:
                        super().quit()
                    finally:
                        # 重置socket状态
                        if hasattr(socket, '_orig_socket'):
                            socket.socket = socket._orig_socket
                            time.sleep(1)
            
            return ProxySMTP_SSL
            
        except Exception as e:
            print(f"代理设置失败: {str(e)}")
            return None

    return None  # 如果没有代理，返回 None

def is_valid_email(email):
    """验证邮箱格式"""
    # 基本格式验证
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(pattern, email):
        return False, "格式无效"
        
    try:
        local_part, domain = email.split('@')
        
        # 检查度限制
        if len(email) > 254 or len(local_part) > 64:
            return False, "邮箱长度超出限制"
            
        # 检查域名是否为常见域名
        if domain.lower() not in COMMON_EMAIL_DOMAINS:
            return False, f"不常见的邮���域名: {domain}"
            
        # 检查本地部分格式
        if local_part.startswith('.') or local_part.endswith('.'):
            return False, "本地部分不能以点号开始或结束"
            
        if '..' in local_part:
            return False, "本地部分不能包含连续的点号"
            
        return True, None
    except Exception:
        return False, "解析失败"

class EmailSender:
    def __init__(self, config):
        self.config = config
        self.from_list = config['smtp']['from_list']
        self.current_from_index = 0
        self.passwords = config['smtp']['passwords']  # 每个邮箱对应的密码
    
    def get_next_from(self):
        """获取下一个发件人"""
        from_info = self.from_list[self.current_from_index]
        password = self.passwords[from_info['email']]  # 获取对应的密码
        self.current_from_index = (self.current_from_index + 1) % len(self.from_list)
        return from_info, password

class EmailError(Exception):
    """邮件发送错误基类"""
    def __init__(self, message, is_permanent=False):
        self.message = message
        self.is_permanent = is_permanent

class SMTPError(EmailError):
    """SMTP错误"""
    pass

class ProxyError(EmailError):
    """代理错误"""
    pass

def send_mail(smtp_handler, config, to_addr, html_content, proxy_info=None, max_retries=3):
    """发送单封邮件"""
    try:
        is_valid, reason = is_valid_email(to_addr)
        if not is_valid:
            print(f"跳过邮箱 {to_addr}: {reason}")
            return False, "invalid_format"
        
        # 获取发件人信息密码
        from_info, password = email_sender.get_next_from()
        
        msg = MIMEMultipart()
        msg['From'] = f"{from_info['name']} <{from_info['email']}>"
        msg['To'] = to_addr
        msg['Subject'] = Header(config['setting']['subject'], 'utf-8')
        msg['Date'] = email_utils.formatdate()
        msg['Message-ID'] = email_utils.make_msgid()
        
        msg.attach(MIMEText(html_content, 'html', 'utf-8'))
        
        for attempt in range(max_retries):
            try:
                # 如果有代理就使用代理，否则使用直连
                server_class = smtp_handler if smtp_handler else smtplib.SMTP_SSL
                with server_class(config['smtp']['host'], config['smtp']['port'], timeout=30) as server:
                    server.login(from_info['email'], password)
                    time.sleep(1)
                    server.send_message(msg)
                    if smtp_handler and proxy_info:  # 如果使用代理���有代理IP
                        print(f"发送成功: {to_addr}，发件人: {from_info['email']}，通过代理 {proxy_info} 发送")
                    else:
                        print(f"发送成功: {to_addr}，发件人: {from_info['email']}，直连模式")
                    time.sleep(1)
                    return True, "success"
            except smtplib.SMTPAuthenticationError:
                raise SMTPError("认证失败", is_permanent=True)
            except smtplib.SMTPServerDisconnected:
                raise SMTPError("服务器连接断开")
            except smtplib.SMTPException as e:
                raise SMTPError(f"SMTP错误: {str(e)}")
            except socket.error as e:
                raise ProxyError(f"代理连接错误: {str(e)}")
            except Exception as e:
                raise EmailError(f"未知错误: {str(e)}")
            finally:
                if attempt == max_retries - 1:
                    return False, "failed"
                time.sleep(5)
    except EmailError as e:
        print(f"发送失败: {to_addr}, 错误: {e.message}")
        return False, e.message
    return False, "failed"

class ProxyManager:
    def __init__(self, proxy_list, max_workers=5):
        self.proxy_list = proxy_list
        self.max_workers = max_workers
        self.working_proxies = []
        self.proxy_ips = {}
        self.current_index = 0
        self.max_fails = 3
        
    def test_all_proxies(self, smtp_host, smtp_port):
        """并发测试所有代理"""
        logger.info("开始并发测试代理连通性...")
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = []
            for proxy in self.proxy_list:
                futures.append(
                    executor.submit(test_proxy_connection, proxy, smtp_host, smtp_port)
                )
            
            for proxy, future in zip(self.proxy_list, futures):
                try:
                    success, proxy_type, real_ip = future.result(timeout=10)
                    if success:
                        self.working_proxies.append((proxy, proxy_type, real_ip))
                        self.proxy_ips[proxy] = real_ip
                except Exception as e:
                    logger.error(f"代理测试失败: {proxy}, 错误: {str(e)}")
                    
        logger.info(f"代理测试完成: {len(self.working_proxies)}/{len(self.proxy_list)} 个可用")
        return len(self.working_proxies) > 0
        
    def get_next_proxy(self):
        """获取下一个代理"""
        if not self.working_proxies:
            return None, None, None
            
        proxy = self.working_proxies[self.current_index]
        self.current_index = (self.current_index + 1) % len(self.working_proxies)
        return proxy
        
    def mark_proxy_failure(self, proxy):
        """标记代理失败"""
        self.proxy_failures[proxy] = self.proxy_failures.get(proxy, 0) + 1
        if self.proxy_failures[proxy] >= self.max_fails:
            logger.warning(f"代理 {proxy} 失败次数过多，移除")
            self.working_proxies = [p for p in self.working_proxies if p[0] != proxy]
            self.current_index = self.current_index % len(self.working_proxies) if self.working_proxies else 0

def setup_logging():
    """设置日志系统"""
    log_format = '%(asctime)s - %(levelname)s - %(message)s'
    logging.basicConfig(
        level=logging.INFO,
        format=log_format,
        handlers=[
            logging.FileHandler('mail_sender.log', encoding='utf-8'),
            logging.StreamHandler()  # 同时输出到控制台
        ]
    )
    
    # 禁用第三方库的警告日志
    logging.getLogger('urllib3').setLevel(logging.ERROR)
    logging.getLogger('requests').setLevel(logging.ERROR)
    
    # 返回 logger 对象
    return logging.getLogger(__name__)

# 创建全局 logger 对象
logger = setup_logging()

class EmailStats:
    def __init__(self):
        self.total = 0
        self.success = 0
        self.failed = {}  # {email: reason}
        self.start_time = time.time()
        self.current_rate = 0
        self.failed_proxies = set()
        
    def add_success(self, email):
        self.success += 1
        self.update_rate()
        
    def add_failure(self, email, reason):
        self.failed[email] = reason
        self.update_rate()
        
    def update_rate(self):
        elapsed = time.time() - self.start_time
        self.current_rate = (self.success + len(self.failed)) / elapsed * 60
        
    def get_report(self):
        elapsed = time.time() - self.start_time
        return {
            'total_processed': self.success + len(self.failed),
            'success': self.success,
            'failed': len(self.failed),
            'current_rate': self.current_rate,
            'elapsed_time': elapsed,
            'failed_details': self.failed
        }
        
    def save_failed_emails(self):
        """保存失败的邮箱到文件"""
        with open('failed_emails.txt', 'w', encoding='utf-8') as f:
            for email, reason in self.failed.items():
                f.write(f"{email}\t{reason}\n")

class RateAdjuster:
    def __init__(self, initial_limit, min_limit=10, max_limit=100):
        self.current_limit = initial_limit
        self.min_limit = min_limit
        self.max_limit = max_limit
        self.success_streak = 0
        self.failure_streak = 0
        
    def adjust_rate(self, success):
        if success:
            self.success_streak += 1
            self.failure_streak = 0
            if self.success_streak >= 10:
                self.increase_rate()
        else:
            self.failure_streak += 1
            self.success_streak = 0
            if self.failure_streak >= 3:
                self.decrease_rate()
                
    def increase_rate(self):
        self.current_limit = min(self.current_limit * 1.2, self.max_limit)
        logger.info(f"提高发送速率至: {self.current_limit:.1f}/分钟")
        
    def decrease_rate(self):
        self.current_limit = max(self.current_limit * 0.8, self.min_limit)
        logger.info(f"降低发送速率至: {self.current_limit:.1f}/分钟")
        
    def get_delay(self):
        return 60 / self.current_limit if self.current_limit > 0 else 0

def confirm_direct_connection():
    """询问用户是否使用直连模式"""
    while True:
        response = input("\n没有可用代理，使用直连模式发送? (y/n): ").lower().strip()
        if response == 'y':
            return True
        elif response == 'n':
            return False
        print("请输入 y 或 n")

def update_email_file(config, processed_emails, invalid_emails, success_emails):
    """更新邮箱文件，移除已处理和无效的邮箱"""
    try:
        with open(config['setting']['email_list'], 'r', encoding='utf-8') as f:
            all_emails = [line.strip() for line in f if line.strip()]
            
        # 过滤掉已处理和无效的邮箱
        remaining_emails = [
            email for email in all_emails 
            if email not in processed_emails 
            and email not in invalid_emails
        ]
        
        # 写入剩余邮箱
        with open(config['setting']['email_list'], 'w', encoding='utf-8') as f:
            f.write('\n'.join(remaining_emails))
            
        logger.info(f"更新邮箱文件，剩余 {len(remaining_emails)} 个地址")
        
        # 保存无效邮箱到单独文件
        with open('invalid_emails.txt', 'w', encoding='utf-8') as f:
            for email, reason in invalid_emails.items():
                f.write(f"{email}\t{reason}\n")
                
        # 保存发送成功的邮箱
        with open('success_emails.txt', 'a', encoding='utf-8') as f:
            for email in success_emails:
                f.write(f"{email}\n")
                
    except Exception as e:
        logger.error(f"更新邮箱文件失败: {str(e)}")

def validate_config(config):
    """验证配置文件的完整性和正确性"""
    required = {
        'smtp': {
            'host': str,
            'port': int,
            'from_list': list,
            'passwords': dict
        },
        'setting': {
            'email_list': str,
            'subject': str,
            'email_content': str,
            'limit': int,
            'max_retries': int,
            'retry_delay': int
        },
        'proxy': {
            'enabled': bool,
            'proxy_list': list
        }
    }
    
    for section, fields in required.items():
        if section not in config:
            raise ValueError(f"配置缺少 {section} 部分")
            
        for field, field_type in fields.items():
            if field not in config[section]:
                raise ValueError(f"配置缺少 {section}.{field} 字段")
            if not isinstance(config[section][field], field_type):
                raise ValueError(f"{section}.{field} 字段类型错误，应为 {field_type.__name__}")

class EmailCache:
    def __init__(self):
        self._content = None
        self._template = None
        self._last_modified = None
        
    def get_content(self, file_path):
        """获取邮件内容，支持缓存"""
        current_mtime = os.path.getmtime(file_path)
        
        if (self._content is None or 
            self._last_modified != current_mtime):
            with open(file_path, 'r', encoding='utf-8') as f:
                self._content = f.read()
            self._last_modified = current_mtime
            
        return self._content

class StateManager:
    def __init__(self, state_file='sender_state.json'):
        self.state_file = state_file
        
    def save_state(self, data):
        """保存当前状态"""
        state = {
            'timestamp': time.time(),
            'processed_emails': list(data['processed_emails']),
            'success_emails': list(data['success_emails']),
            'failed_emails': data['failed_emails'],
            'current_index': data['current_index']
        }
        
        with open(self.state_file, 'w', encoding='utf-8') as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
            
    def load_state(self):
        """加载上次状态"""
        try:
            with open(self.state_file, 'r', encoding='utf-8') as f:
                state = json.load(f)
                return {
                    'processed_emails': set(state['processed_emails']),
                    'success_emails': set(state['success_emails']),
                    'failed_emails': state['failed_emails'],
                    'current_index': state['current_index']
                }
        except FileNotFoundError:
            return None

if __name__ == "__main__":
    # 加载并验证配置
    config = toml.load("config.toml")
    validate_config(config)
    
    # 初始化各个管理器
    email_cache = EmailCache()
    state_manager = StateManager()
    
    # 尝试加载上次状态
    state = state_manager.load_state()
    if state:
        processed_emails = state['processed_emails']
        success_emails = state['success_emails']
        current_index = state['current_index']
    else:
        processed_emails = set()
        success_emails = set()
        current_index = 0
    
    # 读取邮箱列表并过滤无效地址
    try:
        with open(config['setting']['email_list'], "r", encoding="utf-8") as f:
            emails = [line.strip() for line in f if line.strip()]
            # 过滤无效邮箱
            valid_emails = []
            invalid_emails = {}  # 用字典来存储无效原因
            
            for email in emails:
                is_valid, reason = is_valid_email(email)
                if is_valid:
                    valid_emails.append(email)
                else:
                    invalid_emails[email] = reason
            
            if invalid_emails:
                print("\n无效邮箱表：")
                # 按无效原因分类显示
                by_reason = {}
                for email, reason in invalid_emails.items():
                    by_reason.setdefault(reason, []).append(email)
                
                for reason, email_list in by_reason.items():
                    print(f"\n{reason}:")
                    for email in email_list:
                        print(f"  - {email}")
                print()  # 空行
                    
                # 立即保存无效邮箱到文件
                with open('invalid_emails.txt', 'w', encoding='utf-8') as f:
                    for email, reason in invalid_emails.items():
                        f.write(f"{email}\t{reason}\n")
                
                # 立即更新邮箱列表文件，只保留有效邮箱
                with open(config['setting']['email_list'], 'w', encoding='utf-8') as f:
                    f.write('\n'.join(valid_emails))
                
            print(f"共读取到{len(emails)}个邮箱，其中有效邮箱{len(valid_emails)}个，无效邮箱{len(invalid_emails)}个")
            emails = valid_emails
    except FileNotFoundError:
        print("读取邮箱列表失败")
        exit()
    
    if not emails:
        print("邮箱列表为空")
        exit()
    print(f"共读取到{len(emails)}封邮箱")
    
    # 读取邮件内容
    try:
        with open(config['setting']['email_content'], "r", encoding="utf-8") as f:
            html_content = f.read()
    except FileNotFoundError:
        print("读取邮件内容失败")
        exit()
    
    # 获取代理列表并测试连通性
    proxy_list = config.get("proxy", {}).get("proxy_list", [])
    working_proxies = []  # 初始化working_proxies变量
    
    if proxy_list:
        print("开始测试代理连通性...")
        for proxy in proxy_list:
            success, proxy_type, real_ip = test_proxy_connection(proxy, config['smtp']['host'], config['smtp']['port'])
            if success:
                working_proxies.append((proxy, proxy_type, real_ip))  # 保存真实出口IP
        
        if not working_proxies:
            print("没有可用代理，程序退出")
            exit()
        
        print(f"可用代理数量: {len(working_proxies)}/{len(proxy_list)}")
    else:
        print("未配置代理，将直接连SMTP服务器")
    
    # 计算发送延迟
    delay = (60 / config['setting']['limit']) if config['setting']['limit'] != 0 else 0
    total_emails = len(emails)
    print(f"延迟{delay}秒发送，{total_emails}封邮件")
    
    # 初始化统计和管理器
    stats = EmailStats()
    proxy_manager = ProxyManager(proxy_list)
    proxy_manager.working_proxies = working_proxies  # 将测试到的可用代理添加到代理管理器
    proxy_manager.current_index = 0  # 重置索引
    rate_adjuster = RateAdjuster(config['setting']['limit'])
    
    # 初始化发件人管理器
    email_sender = EmailSender(config)
    
    # 记录处理过的邮件和无效邮箱
    processed_emails = set()
    invalid_emails = {}
    success_emails = set()  # 添加成功邮箱集合
    
    # 先处理无效邮箱
    for email in emails:
        is_valid, reason = is_valid_email(email)
        if not is_valid:
            invalid_emails[email] = reason
    
    # 更新次文件，移除无效邮箱
    update_email_file(config, processed_emails, invalid_emails, [])
    
    # 开始发送循环
    for i, email in enumerate(tqdm(emails), start=1):
        if email in invalid_emails:
            continue
            
        success = False
        retry_count = 0
        while not success and retry_count < config['setting']['max_retries']:
            current_proxy = proxy_manager.get_next_proxy()
            proxy_ip = None
            
            if current_proxy[0]:  # 如果有可用代理
                smtp_handler = create_smtp_handler(*current_proxy[:2])
                proxy_ip = current_proxy[2]  # 使用保存的真实出口IP
            else:
                # 询问是否使用直连
                if not hasattr(proxy_manager, 'direct_mode_confirmed'):
                    if confirm_direct_connection():
                        proxy_manager.direct_mode_confirmed = True
                        smtp_handler = smtplib.SMTP_SSL
                    else:
                        print("用户取消发送")
                        exit()
                else:
                    smtp_handler = smtplib.SMTP_SSL
            
            try:
                success, result = send_mail(smtp_handler, config, email, html_content, proxy_ip)
                processed_emails.add(email)  # 添加到已处理集合
                if success:
                    stats.add_success(email)
                    success_emails.add(email)  # 添加到成功集合
                else:
                    stats.add_failure(email, result)
                rate_adjuster.adjust_rate(success)
            except Exception as e:
                logger.error(f"发送异常: {str(e)}")
                if current_proxy[0]:
                    proxy_manager.mark_proxy_failure(current_proxy[0])
                retry_count += 1
                time.sleep(config['setting']['retry_delay'])
        
        # 每发送10封邮件更新一次文件
        if i % 10 == 0:
            update_email_file(config, processed_emails, invalid_emails, success_emails)
    
    # 最后一次更新文件
    update_email_file(config, processed_emails, invalid_emails, [])
    
    # 生成报告
    report = stats.get_report()
    logger.info("\n发送统计报告:")
    logger.info(f"总处理邮箱: {report['total_processed']}")
    logger.info(f"发送成功: {report['success']}")
    logger.info(f"发送失败: {report['failed']}")
    logger.info(f"平均速率: {report['current_rate']:.1f} 封/分钟")
    logger.info(f"总耗时: {report['elapsed_time']:.1f} 秒")
    
    # 保存失败邮箱
    stats.save_failed_emails()
    
    # 定期保存状态
    try:
        for i, email in enumerate(emails[current_index:], start=current_index):
            # ... 发送逻辑 ...
            
            # 每10封邮件保存一次状态
            if i % 10 == 0:
                state_manager.save_state({
                    'processed_emails': processed_emails,
                    'success_emails': success_emails,
                    'failed_emails': stats.failed,
                    'current_index': i
                })
    except KeyboardInterrupt:
        # 保存中断时的状态
        state_manager.save_state({
            'processed_emails': processed_emails,
            'success_emails': success_emails,
            'failed_emails': stats.failed,
            'current_index': i
        })
        raise
