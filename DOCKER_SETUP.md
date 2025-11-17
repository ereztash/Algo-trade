# מדריך Docker להפעלת מערכת Algo-Trade

## תוכן עניינים
- [סקירה כללית](#סקירה-כללית)
- [דרישות מקדימות](#דרישות-מקדימות)
- [התקנה מהירה](#התקנה-מהירה)
- [ארכיטקטורת השירותים](#ארכיטקטורת-השירותים)
- [הגדרת סביבה](#הגדרת-סביבה)
- [הפעלת המערכת](#הפעלת-המערכת)
- [ניטור ובדיקות](#ניטור-ובדיקות)
- [פתרון בעיות](#פתרון-בעיות)
- [פריסה לייצור](#פריסה-לייצור)

---

## סקירה כללית

מערכת ה-Docker Compose כוללת 5 שירותים עיקריים:

1. **Zookeeper** - שירות תיאום עבור Kafka
2. **Kafka** - Message broker לתקשורת בין-שירותית
3. **Prometheus** - איסוף מטריקות וניטור
4. **Algo-Trade App** - האפליקציה הראשית (Data Plane + Order Plane + Strategy)
5. **PostgreSQL** - בסיס נתונים להתמדה (אופציונלי)

---

## דרישות מקדימות

### תוכנות נדרשות
- **Docker**: גרסה 20.10 ומעלה
- **Docker Compose**: גרסה 2.0 ומעלה
- **IBKR TWS/Gateway**: מותקן ומופעל (לחיבור לברוקר)

### בדיקת התקנה
```bash
docker --version
docker-compose --version
```

---

## התקנה מהירה

### 1. שכפול הפרויקט
```bash
git clone <repository-url>
cd Algo-trade
```

### 2. הגדרת משתני סביבה
```bash
# העתק את קובץ הדוגמה
cp .env.example .env

# ערוך את הקובץ עם הערכים שלך
nano .env  # או vi, vim, code, etc.
```

### 3. הרצת המערכת
```bash
# בניה והפעלה של כל השירותים
docker-compose up -d

# בדיקת סטטוס השירותים
docker-compose ps

# צפייה בלוגים
docker-compose logs -f algo-trade
```

---

## ארכיטקטורת השירותים

### תרשים זרימה
```
┌─────────────┐
│   IBKR TWS  │
│  (External) │
└──────┬──────┘
       │
       ▼
┌─────────────────────────────────────────────┐
│         Algo-Trade Application              │
│  ┌───────────────────────────────────────┐  │
│  │  Data Plane                           │  │
│  │  - IBKR Connectors                    │  │
│  │  - Normalization                      │  │
│  │  - QA Gates                           │  │
│  └───────────┬───────────────────────────┘  │
│              │                               │
│              ▼                               │
│  ┌───────────────────────────────────────┐  │
│  │        Kafka Message Bus              │◄─┼─── Kafka Container
│  └───────────┬───────────────────────────┘  │
│              │                               │
│              ▼                               │
│  ┌───────────────────────────────────────┐  │
│  │  Order Plane                          │  │
│  │  - Risk Checks                        │  │
│  │  - Execution                          │  │
│  └───────────┬───────────────────────────┘  │
│              │                               │
│              ▼                               │
│  ┌───────────────────────────────────────┐  │
│  │  Strategy Loop                        │  │
│  │  - Signal Generation                  │  │
│  │  - Portfolio Optimization             │  │
│  └───────────────────────────────────────┘  │
└───────────────┬───────────────────────────┬─┘
                │                           │
                ▼                           ▼
        ┌───────────────┐         ┌──────────────┐
        │  Prometheus   │         │  PostgreSQL  │
        │   (Metrics)   │         │  (Storage)   │
        └───────────────┘         └──────────────┘
```

### פרטי פורטים
| שירות | פורט | תיאור |
|-------|------|--------|
| Zookeeper | 2181 | Kafka coordination |
| Kafka | 9092, 9093 | Message broker (internal & external) |
| Prometheus | 9090 | Metrics & monitoring UI |
| Algo-Trade | 8000 | Prometheus metrics endpoint |
| Algo-Trade | 8080 | Health check & API |
| PostgreSQL | 5432 | Database |

---

## הגדרת סביבה

### משתני סביבה קריטיים

#### חיבור ל-IBKR
```bash
# קובץ .env
IBKR_HOST=host.docker.internal  # לחיבור למחשב המארח
IBKR_PORT=7497                   # TWS Paper Trading
# או
IBKR_PORT=4002                   # IB Gateway Paper Trading
IBKR_CLIENT_ID=1
```

**הערה חשובה**: השתמש ב-`host.docker.internal` כדי לגשת ל-TWS/Gateway שרץ על המחשב המארח.

#### Kafka
```bash
KAFKA_BOOTSTRAP_SERVERS=kafka:9092
KAFKA_AUTO_OFFSET_RESET=earliest
```

#### בסיס נתונים
```bash
DB_HOST=postgres
DB_PORT=5432
DB_NAME=algo_trade
DB_USER=postgres
DB_PASSWORD=<your-secure-password>
```

---

## הפעלת המערכת

### פקודות בסיסיות

#### הפעלה
```bash
# הפעלה רגילה (ברקע)
docker-compose up -d

# הפעלה עם rebuild
docker-compose up -d --build

# הפעלה עם לוגים
docker-compose up
```

#### עצירה
```bash
# עצירת כל השירותים
docker-compose down

# עצירה עם מחיקת volumes
docker-compose down -v

# עצירת שירות ספציפי
docker-compose stop algo-trade
```

#### צפייה בלוגים
```bash
# כל השירותים
docker-compose logs -f

# שירות ספציפי
docker-compose logs -f algo-trade

# 100 שורות אחרונות
docker-compose logs --tail=100 algo-trade
```

#### כניסה לקונטיינר
```bash
# Shell interactif
docker-compose exec algo-trade /bin/bash

# הרצת פקודה בודדת
docker-compose exec algo-trade python --version
```

### הרצת שירותים נבחרים

```bash
# רק Kafka + Zookeeper
docker-compose up -d zookeeper kafka

# רק האפליקציה (בהנחה ש-Kafka כבר רץ)
docker-compose up -d algo-trade
```

---

## ניטור ובדיקות

### Prometheus
גישה ל-Prometheus UI:
```
http://localhost:9090
```

שאילתות שימושיות:
```promql
# CPU usage
rate(process_cpu_seconds_total[5m])

# Memory usage
process_resident_memory_bytes

# Kafka messages
kafka_messages_total

# Fill latency
histogram_quantile(0.95, rate(fill_latency_ms_bucket[5m]))
```

### Health Checks

#### בדיקת בריאות שירותים
```bash
# כל השירותים
docker-compose ps

# בדיקת health status
docker inspect --format='{{.State.Health.Status}}' algo-trade-app

# API health endpoint
curl http://localhost:8080/health
```

#### בדיקת Kafka
```bash
# רשימת topics
docker-compose exec kafka kafka-topics --list --bootstrap-server localhost:9092

# פרטי topic
docker-compose exec kafka kafka-topics --describe --topic order_intents --bootstrap-server localhost:9092

# צריכת הודעות (לבדיקה)
docker-compose exec kafka kafka-console-consumer --bootstrap-server localhost:9092 --topic order_intents --from-beginning
```

### בדיקת חיבור ל-IBKR
```bash
# הרצת סקריפט בדיקה
docker-compose exec algo-trade python -c "
from algo_trade.core.execution.IBKR_handler import IBKRHandler
handler = IBKRHandler()
handler.connect()
print('Connection status:', handler.ib.isConnected())
handler.disconnect()
"
```

---

## פתרון בעיות

### בעיות נפוצות

#### 1. קונטיינר לא עולה
```bash
# בדיקת לוגים
docker-compose logs <service-name>

# restart שירות
docker-compose restart <service-name>

# rebuild מלא
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

#### 2. שגיאת חיבור ל-Kafka
```bash
# בדיקה ש-Kafka רץ
docker-compose ps kafka

# בדיקת health
docker-compose exec kafka kafka-broker-api-versions --bootstrap-server localhost:9092

# restart Kafka + Zookeeper
docker-compose restart zookeeper kafka
```

#### 3. שגיאת חיבור ל-IBKR
- ודא ש-TWS/Gateway רץ על המחשב המארח
- בדוק שהפורט נכון (7497 או 4002)
- ודא שהגדרת API מאופשרת ב-TWS
- בדוק firewall settings

#### 4. בעיות זיכרון
```bash
# בדיקת שימוש במשאבים
docker stats

# הגדלת זיכרון ל-Docker Desktop
# Settings -> Resources -> Memory -> 4GB+
```

#### 5. בעיות הרשאות (Linux)
```bash
# הוספת משתמש ל-docker group
sudo usermod -aG docker $USER

# logout ו-login מחדש
```

### לוגים ודיבאג

#### הפעלה במצב debug
```bash
# ערוך .env
DEBUG=true
LOG_LEVEL=DEBUG

# restart
docker-compose down
docker-compose up -d
docker-compose logs -f
```

#### שמירת לוגים לקובץ
```bash
docker-compose logs > logs_$(date +%Y%m%d_%H%M%S).txt
```

---

## פריסה לייצור

### שיקולים לייצור

#### 1. אבטחה
```yaml
# docker-compose.prod.yml
services:
  algo-trade:
    environment:
      - DEBUG=false
      - LOG_LEVEL=WARNING
    # הסרת port mappings מיותרים
    ports:
      - "127.0.0.1:8000:8000"  # bind רק ל-localhost
```

#### 2. משאבים
```yaml
services:
  algo-trade:
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 4G
        reservations:
          cpus: '1'
          memory: 2G
```

#### 3. Restart Policy
```yaml
services:
  algo-trade:
    restart: always
    deploy:
      restart_policy:
        condition: on-failure
        delay: 5s
        max_attempts: 3
```

#### 4. Secrets Management
```bash
# השתמש ב-Docker secrets במקום .env
docker secret create db_password /path/to/password.txt
```

### פריסה ל-Cloud

#### AWS ECS
```bash
# התקנת ecs-cli
ecs-cli compose --file docker-compose.yml up

# או השתמש ב-AWS Fargate
```

#### Kubernetes
```bash
# המרה ל-Kubernetes manifests
kompose convert -f docker-compose.yml

# או צור Helm chart
helm create algo-trade
```

#### Google Cloud Run
```bash
# build ו-push
docker build -t gcr.io/[PROJECT-ID]/algo-trade .
docker push gcr.io/[PROJECT-ID]/algo-trade

# deploy
gcloud run deploy algo-trade --image gcr.io/[PROJECT-ID]/algo-trade
```

---

## גיבוי ושחזור

### גיבוי Volumes
```bash
# גיבוי PostgreSQL
docker-compose exec postgres pg_dump -U postgres algo_trade > backup_$(date +%Y%m%d).sql

# גיבוי Kafka data
docker run --rm -v algo-kafka-data:/data -v $(pwd):/backup ubuntu tar czf /backup/kafka_backup.tar.gz /data
```

### שחזור
```bash
# שחזור PostgreSQL
docker-compose exec -T postgres psql -U postgres algo_trade < backup_20241117.sql

# שחזור Kafka
docker run --rm -v algo-kafka-data:/data -v $(pwd):/backup ubuntu tar xzf /backup/kafka_backup.tar.gz -C /
```

---

## משאבים נוספים

- [Docker Documentation](https://docs.docker.com/)
- [Docker Compose Reference](https://docs.docker.com/compose/compose-file/)
- [Kafka Docker Quickstart](https://developer.confluent.io/quickstart/kafka-docker/)
- [Prometheus Docker](https://prometheus.io/docs/prometheus/latest/installation/#using-docker)
- [IBKR API Documentation](https://www.interactivebrokers.com/en/index.php?f=5041)

---

## תמיכה

לבעיות או שאלות:
1. בדוק את [פתרון בעיות](#פתרון-בעיות)
2. עיין בלוגים: `docker-compose logs`
3. פתח issue ב-GitHub repository
