# 🧪 דוח בדיקות ואימות — Hotel Platform (GitOps)

> **מטרה:** לתעד בצורה מסודרת מה נבדק, איך נבדק, אילו תקלות התרחשו בדרך ואיך תוקנו — כך שאפשר לשחזר את כל האימות מאפס.
>
> **תאריך הרצה:** 2026-07-12 · **מבצע הבדיקה:** אימות מול קלאסטר חי
> **סביבה:** Docker Desktop Kubernetes (`kubectl` context: `docker-desktop`) + Docker Compose מקומי

---

## 1. שיטת הבדיקה (Methodology)

האימות נעשה בשתי רמות, מהתשתית ועד לפונקציונליות בפועל:

| רמה | מה נבדק | הכלי |
|-----|----------|------|
| **GitOps / CD** | שה-ArgoCD Application במצב `Synced / Healthy` ומנהל את כל ה-stack | `kubectl get applications` |
| **Kubernetes runtime** | שכל ה-Pods, Deployments וה-Job רצים ובריאים ב-namespace `hotel` | `kubectl get all -n hotel` |
| **Traceability** | שה-image שרץ על הקלאסטר תואם בדיוק ל-SHA של הקומיט האחרון ב-`main` | `kubectl get deployment ... -o jsonpath` + `git log` |
| **Data seeding** | שה-Seed Job אידמפוטנטי (לא מכפיל נתונים בהרצה חוזרת) | `kubectl logs job/hotel-seed` |
| **Functional** | שה-API באמת מחזיר תשובות (`/health`, `/hotels`) — לא רק ש"ה-Pod רץ" | `kubectl port-forward` + `curl` |

> ⚠️ **הערת יושרה — מה לא נבדק בהרצה הזו:** ה-CI (GitHub Actions לבנייה, smoke test, ופתיחת PR) חי ב-repos של האפליקציה (`hotel-backend` / `hotel-frontend`), לא ברפו התשתית הזה — לכן ה-CI עצמו לא הורץ כאן, אלא **אומתו התוצרים שלו** (ה-PRs האוטומטיים #1 ו-#2). כמו כן לא הודמה תקלה יזומה כדי לבדוק `selfHeal`/`prune` בזמן אמת, ולא נבדקה כניסה דרך ה-hostname `hotel.local` ב-Ingress.

---

## 2. תוצאות האימות — סיכום

| # | בדיקה | תוצאה שהתקבלה | סטטוס |
|---|-------|----------------|:------:|
| 1 | ArgoCD Application | `hotel` → **Synced / Healthy** | ✅ |
| 2 | Backend Deployment | `1/1` Running | ✅ |
| 3 | Frontend Deployment | `5/5` Running (5 replicas) | ✅ |
| 4 | MongoDB Deployment | `1/1` Running (מגובה ב-PVC) | ✅ |
| 5 | Seed Job | `Complete 1/1` | ✅ |
| 6 | התאמת Image ↔ Commit SHA | תג על הקלאסטר == הקומיט האחרון שמוזג | ✅ |
| 7 | אידמפוטנטיות ה-Seed | `exists ×4`, `total hotels: 4` (אין כפילויות) | ✅ |
| 8 | Backend `/health` | `{"status":"ok"}` (k8s + compose) | ✅ |
| 9 | Backend `/hotels` | מחזיר JSON עם רשימת מלונות | ✅ |

**מסקנה:** כל תשע הבדיקות עברו. המערכת במצב `Synced / Healthy` ומתפקדת מקצה לקצה.

---

## 3. הפלט הגולמי (Raw evidence)

### 3.1 ArgoCD — מצב הסנכרון

```console
$ kubectl get applications -n argocd
NAME    SYNC STATUS   HEALTH STATUS
hotel   Synced        Healthy
```

### 3.2 כל המשאבים ב-namespace `hotel`

```console
$ kubectl get all -n hotel
NAME                                  READY   STATUS      RESTARTS      AGE
pod/backend-b9b4999b-hjb4n            1/1     Running     0             12m
pod/hotel-frontend-76cfd9854f-2x9zj   1/1     Running     0             25m
pod/hotel-frontend-76cfd9854f-mffrn   1/1     Running     0             25m
pod/hotel-frontend-76cfd9854f-qwp4n   1/1     Running     0             25m
pod/hotel-frontend-76cfd9854f-tvvt5   1/1     Running     0             25m
pod/hotel-frontend-76cfd9854f-v9pwb   1/1     Running     0             25m
pod/hotel-seed-hcbjt                  0/1     Completed   0             5m19s
pod/mongodb-7598fd59d9-cm5tp          1/1     Running     7 (54m ago)   13d

deployment.apps/backend          1/1     1            1           12d
deployment.apps/hotel-frontend   5/5     5            5           5d
deployment.apps/mongodb          1/1     1            1           13d

job.batch/hotel-seed   Complete   1/1   5s   5m19s
```

### 3.3 הוכחת Traceability — התג שרץ תואם לקומיט

```console
$ kubectl get deployment backend -n hotel \
    -o=jsonpath="{.spec.template.spec.containers[0].image}"
dolevatik/hotel-backend:c2c216203a6c07a2b9b973dc4be1e2ef82d1f13c

$ git log --oneline -1 --grep="Update backend image"
002eb13 Update backend image to c2c216203a6c07a2b9b973dc4be1e2ef82d1f13c
```

> ה-SHA שרץ על הקלאסטר (`c2c216203…`) **זהה בדיוק** ל-SHA בקומיט האחרון שמוזג ל-`main`. זו ההוכחה שכל Pod שרץ ניתן לעקיבה עד קומיט מקור מדויק — הלב של GitOps, בלי `kubectl apply` ידני בדרך.

### 3.4 Seed Job — אידמפוטנטי

```console
$ kubectl logs -n hotel job/hotel-seed
Waiting for MongoDB to accept connections...
MongoDB is up. Seeding hotels (idempotent)...
exists:   Sunset Resort
exists:   Ocean View Hotel
exists:   Mountain Retreat
exists:   City Lights Inn
total hotels: 4
```

> כל ארבעת המלונות כבר קיימים (`exists`) והסה"כ נשאר `4` — כלומר הרצה חוזרת של ה-Job **לא** יוצרת כפילויות. זו התנהגות אידמפוטנטית נכונה.

### 3.5 בדיקה פונקציונלית — ה-API מחזיר נתונים

```console
# דרך port-forward ל-Service ב-Kubernetes
$ kubectl port-forward -n hotel svc/backend 3001:3000 &
$ curl -s http://localhost:3001/health
{"status":"ok"}
$ curl -s http://localhost:3001/hotels
[{"description":"Beachfront resort with sunset views","hotel_id":"...",
  "location":"Eilat","name":"Sunset Resort","price_per_night":520}, ...]

# ה-stack המקומי (Docker Compose) על :3000
$ curl -s http://localhost:3000/health
{"status":"ok"}
```

---

## 4. יומן תקלות ותיקונים (Incident log)

> החלק שהכי שווה ללמידה: ה-pipeline **לא** עבד חלק מהרגע הראשון. התרחשו תקלות אמיתיות, אובחנו ותוקנו. היכולת לאבחן ולתקן היא בדיוק מה שמדגים בשלות DevOps.

| קומיט | התקלה | שורש הבעיה | התיקון |
|-------|--------|-------------|--------|
| `d321d1a` | **ImagePullBackOff** — ה-Pod לא עלה | ה-Deployment הצביע על תג image `:1` שלא היה קיים ב-Docker Hub | הצמדה (pin) לתג `:3` שכן קיים ב-registry |
| `ec041a3` | **תפריט מלונות ריק** (empty dropdown) | ה-frontend לא קיבל נתונים + פיזור manifests | תיקון הזרימה + איחוד כל ה-manifests תחת `k8s/` |
| `8ea1c09` | ריבוי/כפילות של ArgoCD Applications | הוגדרו כמה Applications במקום אחד | איחוד ל-**Application יחיד** שמנהל את כל ה-stack דרך Kustomize |

לאחר התיקונים, ה-GitOps flow עבד מקצה לקצה: ה-PRs האוטומטיים **#1** ו-**#2** ("Update backend image to `<sha>`") הם התוצר של הבוט שפותח PR עם תג ה-SHA — מיזוג = פריסה.

---

## 5. איך לשחזר את האימות (Runbook)

```bash
# 1. מצב ArgoCD
kubectl get applications -n argocd

# 2. מצב כל המשאבים
kubectl get all -n hotel

# 3. הוכחת traceability
kubectl get deployment backend -n hotel \
  -o=jsonpath="{.spec.template.spec.containers[0].image}"; echo
git log --oneline -1 --grep="Update backend image"

# 4. אידמפוטנטיות ה-seed
kubectl logs -n hotel job/hotel-seed

# 5. בדיקה פונקציונלית
kubectl port-forward -n hotel svc/backend 3001:3000 &
curl -s http://localhost:3001/health
curl -s http://localhost:3001/hotels
```

---

## 6. שורה תחתונה

- **הייתה תקלה?** כן — שתי תקלות אמיתיות (`ImagePullBackOff`, תפריט ריק) + ניקוי קונפיגורציה, כולן אובחנו ותוקנו.
- **המצב הנוכחי?** ✅ `Synced / Healthy`, כל ה-Pods רצים, ה-API מחזיר נתונים, וה-image שרץ ניתן לעקיבה עד קומיט מקור מדויק.
- **מה חשוב לזכור לפרויקט הגמר:** הסיפור של *נתקלתי → אבחנתי → תיקנתי → אימתתי* חזק יותר מ"הכול עבד חלק".

---

<div align="center">

*דוח זה מתעד אימות שבוצע מול קלאסטר חי בתאריך 2026-07-12. הפקודות בסעיף 5 מאפשרות שחזור מלא.*

</div>
