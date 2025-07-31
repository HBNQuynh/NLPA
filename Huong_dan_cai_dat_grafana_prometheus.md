# Hướng Dẫn Cài Đặt Grafana & Prometheus Trên Windows và Export Metrics từ Python

## 1. Cài đặt Prometheus trên Windows

### Bước 1: Tải Prometheus

- Truy cập: https://prometheus.io/download/
- Tải phiên bản dành cho Windows (prometheus-x.x.x.windows-amd64.zip)
- Giải nén vào thư mục mong muốn, ví dụ: `C:\prometheus`

### Bước 2: Cấu hình Prometheus

Tạo file `prometheus.yml` trong thư mục Prometheus với nội dung mẫu:

```yaml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: "python_app"
    static_configs:
      - targets: ["localhost:8000"]
```

### Bước 3: Chạy Prometheus

Mở Command Prompt và điều hướng đến thư mục Prometheus, chạy lệnh:

```sh
prometheus.exe --config.file=prometheus.yml
```

Truy cập `http://localhost:9090` để kiểm tra giao diện Prometheus.

---

## 2. Cài đặt Grafana trên Windows

### Bước 1: Tải Grafana

- Truy cập: https://grafana.com/grafana/download
- Chọn Windows, tải file `.zip` hoặc `.exe` installer.

### Bước 2: Cài đặt hoặc giải nén

- Nếu dùng `.exe`: chạy và cài đặt như phần mềm thông thường.
- Nếu dùng `.zip`: giải nén và chạy `bin\grafana-server.exe`

### Bước 3: Truy cập Grafana

- Mở trình duyệt, truy cập `http://localhost:3000`
- Đăng nhập với tài khoản mặc định:
  - **Username:** admin
  - **Password:** admin (sẽ được yêu cầu đổi mật khẩu)

---

## 3. Kết nối Prometheus vào Grafana

### Bước 1: Thêm dữ liệu nguồn

- Vào Grafana > `Configuration` > `Data Sources` > `Add data source`
- Chọn **Prometheus**
- Nhập URL: `http://localhost:9090`
- Nhấn `Save & Test`

---

## 4. Export Metrics từ Ứng Dụng Python

### Bước 1: Cài đặt thư viện

```bash
pip install prometheus_client
```

### Bước 2: Tạo ứng dụng Python mẫu

```python
from prometheus_client import start_http_server, Summary, Counter
import time
import random

# Tạo metric
REQUEST_TIME = Summary('request_processing_seconds', 'Time spent processing request')
REQUEST_COUNT = Counter('my_app_requests_total', 'Total number of requests')

@REQUEST_TIME.time()
def process_request():
    time.sleep(random.random())
    REQUEST_COUNT.inc()

if __name__ == '__main__':
    # Expose metrics tại localhost:8000/metrics
    start_http_server(8000)
    print("Serving metrics on http://localhost:8000/metrics")

    while True:
        process_request()
```

### Bước 3: Cấu hình Prometheus để scrape Python app

Đảm bảo file `prometheus.yml` chứa mục tiêu:

```yaml
static_configs:
  - targets: ["localhost:8000"]
```

---

## 5. Tạo Dashboard Trong Grafana

1. Vào Grafana > `Dashboard` > `New`
2. Thêm panel, sử dụng các metric ví dụ:
   - `my_app_requests_total`
   - `request_processing_seconds`

---

## 6. Import Dashboard từ File JSON

1. Truy cập Grafana, vào `Dashboards` > `Import`.
2. Nhấn nút **Upload JSON file** và chọn file `.json` đã chuẩn bị.
3. Chọn Data Source là Prometheus nếu được yêu cầu.
4. Nhấn **Import** để hoàn tất.

---
