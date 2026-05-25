# Миграция с Render на Fly.io

> Полностью бесплатно. Auto-deploy из GitHub. ~15 минут работы.

## Что мы получаем

| | Render Free Worker | Fly.io Free Tier |
|---|---|---|
| Цена | $7/мес (free убрали) | **$0/мес** |
| RAM | 512MB | 256MB (хватает) |
| Auto-deploy из GitHub | ✅ | ✅ через Actions |
| Spin-down при простое | да (для web; worker — нет) | **нет** |
| Регионы | США/Европа | весь мир, выбираешь сам |

---

## Шаг 1: Установить flyctl локально

### Windows (PowerShell)
```powershell
iwr https://fly.io/install.ps1 -useb | iex
```

### macOS / Linux
```bash
curl -L https://fly.io/install.sh | sh
```

После установки перезапусти терминал и проверь:
```bash
flyctl version
```

---

## Шаг 2: Логин

```bash
flyctl auth login
```
Откроется браузер — авторизуйся через свой Fly.io аккаунт.

---

## Шаг 3: Создать приложение

В корне репозитория:
```bash
flyctl launch --no-deploy
```

Когда спросит — **внимание!**:
- `App name` → введи что-то уникальное (например `ai-disco-bot-ernest`). Запиши его.
- `Region` → выбери ближайший (для России: `fra` Frankfurt, или `ams` Amsterdam)
- `Postgres / Redis` → **No** к обоим (мы используем GitHub-as-DB)
- `Deploy now?` → **No** (мы ещё не передали секреты)

Fly обновит `fly.toml` с твоим реальным именем приложения.

---

## Шаг 4: Перенести env-переменные

Это место, где переменные с Render «переезжают». На Fly они хранятся как **секреты** (зашифровано, никогда не попадают в git).

Открой Render dashboard → твой worker → **Environment**. Скопируй значения каждой переменной.

Затем выполни локально (подставив реальные значения):

```bash
flyctl secrets set \
  BOT_TOKEN="123456789:AAAA..." \
  GITHUB_TOKEN="ghp_..." \
  GITHUB_REPO="ErnestKostevich/telegram-ai-bot-db" \
  GITHUB_FILE_PATH="bot_data.json" \
  CREATOR_ID="123456789"
```

> 💡 **Windows PowerShell:** заменяй `\` на ``` ` ``` (backtick) для переноса строк, или пиши всё одной строкой.

Проверь что секреты установились:
```bash
flyctl secrets list
```
Должен показать имена (значения скрыты — это нормально).

---

## Шаг 5: Остановить Render (важно!)

Перед первым деплоем на Fly **обязательно остановить Render**, иначе два инстанса будут конкурировать за getUpdates и оба упадут с 409 Conflict.

1. Зайди в [Render dashboard](https://dashboard.render.com/worker/srv-d3gimghr0fns73blocmg)
2. Settings → **Suspend Service**
3. Подожди 30 секунд

---

## Шаг 6: Первый деплой

```bash
flyctl deploy
```

Будет:
1. Билд Docker-образа удалённо (1–2 мин)
2. Загрузка на Fly
3. Старт VM
4. Health check

Когда увидишь `Deployment successful` — открой Telegram, напиши боту `/start`. Должен работать.

Логи в реальном времени:
```bash
flyctl logs
```

---

## Шаг 7: Включить auto-deploy через GitHub Actions

Это позволит каждому push в `main` автоматически деплоить на Fly (как сейчас на Render).

### 7.1 Сгенерировать deploy-токен

```bash
flyctl tokens create deploy
```

Скопируй выданную строку (начинается с `fly_...`). Это деплой-токен с минимальными правами.

### 7.2 Добавить в GitHub Secrets

1. Открой репозиторий → **Settings** → **Secrets and variables** → **Actions**
2. **New repository secret**:
   - Name: `FLY_API_TOKEN`
   - Value: вставь токен из шага 7.1
3. Save

### 7.3 Проверить workflow

Файл `.github/workflows/fly-deploy.yml` уже в репо. На любой push в main:
1. GitHub Actions поднимает Ubuntu runner
2. Ставит flyctl
3. Выполняет `flyctl deploy --remote-only`

Чтобы протестировать прямо сейчас — сделай любой пустой коммит и push:
```bash
git commit --allow-empty -m "test fly auto-deploy"
git push
```

Открой Actions tab на GitHub — должен запуститься workflow «Fly Deploy». Через ~2 мин зелёная галочка.

---

## Шаг 8: Удалить Render (через сутки)

Подожди **сутки** работы на Fly. Если за это время бот ни разу не упал:

1. Render dashboard → твой worker → Settings
2. **Delete Service** (внизу страницы, красная кнопка)
3. Также можно удалить env-переменные из Render dashboard если не хочешь чтобы они там лежали (они уже на Fly)

---

## Полезные команды Fly

```bash
flyctl status                    # текущее состояние VM
flyctl logs                      # стрим логов
flyctl secrets list              # список секретов (без значений)
flyctl secrets set KEY=value     # обновить одну переменную
flyctl secrets unset KEY         # удалить
flyctl deploy                    # ручной деплой (обычно автоматом через GH)
flyctl restart                   # перезапустить без передеплоя
flyctl ssh console               # ssh в работающий контейнер
flyctl machine list              # все VM приложения
```

---

## Что делать если что-то пошло не так

### Бот не отвечает после `flyctl deploy`
```bash
flyctl logs
```
Смотри последние ошибки. Скорее всего одно из:
- Один из секретов не установлен (`fly secrets list`)
- Render ещё не остановлен → 409 Conflict
- BOT_TOKEN неверный

### Хочу обратно на Render
1. Render dashboard → **Resume Service**
2. На Fly: `flyctl apps destroy <app-name>` (опционально)

### Логи показывают «Refusing to save: storage was never loaded successfully»
- Значит `GITHUB_TOKEN` или `GITHUB_REPO` неправильные. Проверь:
  ```bash
  flyctl secrets list
  ```
  Если переменных нет — установи их через `flyctl secrets set ...` (шаг 4).

---

## Зачем нам `auto_stop_machines = false`?

Fly по умолчанию останавливает VM при простое (как Heroku когда-то). Для polling-бота это смерть — он не сможет получать обновления. В нашем `fly.toml` нет блока `[http_service]` именно поэтому: бот не слушает HTTP-порт, он сам пингует Telegram. Без http_service VM никогда не уйдёт в sleep.

---

## Стоимость

Fly.io free tier даёт:
- 3 × shared-cpu-1x VM с 256MB RAM
- 160ГБ исходящего трафика
- Никаких лимитов по времени работы

Для нашего бота это ~5% от лимита. Будем умещаться годами.
