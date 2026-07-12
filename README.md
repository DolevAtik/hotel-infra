# hotel-infra

תשתית פריסה (Infrastructure) לאפליקציית מלון, הכוללת **Frontend**, **Backend**, **MongoDB**
ו-**mongo-express**. מיועדת להרצה מקומית עם Docker Compose ולפריסה לקלאסטר Kubernetes
דרך ArgoCD (GitOps).

## מבנה הפרויקט

```
hotel-infra
├── docker-compose.yml          # הרצה מקומית של כל השירותים
├── k8s/
│   ├── namespace.yaml          # namespace בשם hotel
│   ├── frontend/               # Deployment + Service (ClusterIP) + ConfigMap (config.js בזמן ריצה) + Ingress (/ ו-/api)
│   ├── backend/                # Deployment + Service (ClusterIP)
│   ├── mongodb/                # Deployment + Service (ClusterIP) + Secret + PVC
│   └── seed/                   # Job + ConfigMap לזריעת מלונות (אידמפוטנטי)
├── argocd/
│   ├── frontend-app.yaml       # ArgoCD Application ל-frontend (path: k8s/frontend)
│   └── backend-app.yaml        # ArgoCD Application ל-backend (path: k8s/backend)
├── scripts/
│   ├── seed_hotels.js          # זריעת מלונות לדוגמה ל-MongoDB (מקור האמת לנתוני הזריעה)
│   └── smoke_test.py           # בדיקת עשן ל-backend מול MongoDB
├── .env.example                # תבנית למשתני סביבה
└── README.md
```

> **תמונת מצב על הפריסה ל-Kubernetes:** ה-manifests תואמים לקלאסטר הפעיל —
> images מ-Docker Hub (`dolevatik/hotel-backend`, `dolevatik/hotel-frontend`),
> labels בסגנון `app: <component>`, ו-Secret בשם `mongodb-secret`. ה-frontend
> קורא ל-API היחסי `/api` (nginx מפנה ל-`backend:3000`) לפי `config.js` שמוזרק
> מ-ConfigMap בזמן ריצה. הזריעה של המלונות מתבצעת דרך `k8s/seed/` (Job).

## ארכיטקטורה

| רכיב           | תפקיד                       | פורט פנימי | חשיפה (Kubernetes)   |
|----------------|-----------------------------|-----------|----------------------|
| frontend       | ממשק משתמש (React/Nginx)    | 80        | ClusterIP            |
| backend        | API                         | 3000      | ClusterIP            |
| mongodb        | בסיס נתונים                  | 27017     | ClusterIP            |

ה-frontend פונה ל-backend דרך הנתיב היחסי `/api` (nginx בתוך image ה-frontend
מפנה ל-`backend:3000`), וה-backend פונה ל-mongodb. נתוני MongoDB נשמרים על PVC
כדי לשרוד הפעלות מחדש של ה-Pod. השירותים הם `ClusterIP`, והחשיפה החוצה היא דרך
ה-Ingress שב-`k8s/frontend/ingress.yaml` (host `hotel.local`, מחלקה `nginx`) —
`/` מגיע ל-frontend ו-`/api` מנותב ל-`backend:3000` עם הסרת הקידומת. לחלופין
`kubectl port-forward`. (mongo-express קיים רק בהרצה המקומית עם Docker Compose,
לא ב-Kubernetes.)

## הרצה מקומית (Docker Compose)

צור קובץ `.env` באותה תיקייה (אפשר להעתיק מ-`.env.example`):

```env
MONGO_ROOT_USERNAME=admin
MONGO_ROOT_PASSWORD=admin123
ME_USERNAME=admin
ME_PASSWORD=admin123
```

ואז:

```bash
docker compose up -d --build
```

כתובות (לפי הפורטים שמפורסמים ב-`docker-compose.yml`):
- Frontend:      http://localhost:8080
- Backend API:   http://localhost:3000
- mongo-express: http://localhost:8081
- MongoDB:       mongodb://localhost:27017

עצירה:

```bash
docker compose down          # שמירה על הנתונים
docker compose down -v       # מחיקת הנתונים (volume)
```

## פריסה ל-Kubernetes (ידנית)

חשוב להחיל לפי הסדר (namespace ← storage/secret ← workloads ← seed):

```bash
kubectl apply -f k8s/namespace.yaml

kubectl apply -f k8s/mongodb/     # Secret + PVC + Deployment + Service
kubectl apply -f k8s/backend/
kubectl apply -f k8s/frontend/    # Deployment + Service + ConfigMap (config.js) + Ingress

# זריעת מלונות לדוגמה (Job אידמפוטנטי — אפשר להריץ שוב בבטחה):
kubectl apply -f k8s/seed/
```

בדיקה:

```bash
kubectl get all -n hotel
kubectl get pvc -n hotel
kubectl logs -n hotel job/hotel-seed        # פלט הזריעה (inserted/exists + total)

# גישה ל-frontend (ClusterIP): port-forward מקומי
kubectl port-forward -n hotel svc/hotel-frontend 8080:80
# ואז http://localhost:8080
```

## פריסה דרך ArgoCD (GitOps)

1. דחוף את הריפו ל-Git ועדכן את `repoURL` בקבצי `argocd/*.yaml`.
2. החל את האפליקציות:

```bash
kubectl apply -f argocd/frontend-app.yaml
kubectl apply -f argocd/backend-app.yaml
```

ArgoCD יסנכרן אוטומטית (`automated` עם `prune` ו-`selfHeal`) את התיקיות
`k8s/frontend` ו-`k8s/backend` אל ה-namespace `hotel`.

> הערה: ה-Application של ArgoCD מצביעים על תיקיות `frontend`/`backend` בלבד.
> את רכיבי התשתית המשותפים (namespace, mongodb כולל Secret/PVC) ואת ה-Job
> שב-`k8s/seed/` יש להחיל ידנית, או להוסיף עבורם Application/`app-of-apps` נוסף.

## אבטחה

- `k8s/mongodb/secret.yaml` מכיל ערכים לדוגמה בלבד (`admin`/`admin123`). **החלף אותם**
  לפני שימוש אמיתי, ואל תשמור סודות אמיתיים ב-Git. שקול
  [Sealed Secrets](https://github.com/bitnami-labs/sealed-secrets) או
  External Secrets.
- שנה את פרטי ה-Basic Auth של mongo-express בסביבת ייצור (רלוונטי להרצה המקומית עם Docker Compose).
