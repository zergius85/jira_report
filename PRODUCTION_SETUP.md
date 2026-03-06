# 🚀 Настройка production-ветки main

Инструкция по переключению на ветку `main` как основную для продакшена.

---

## 📋 Текущее состояние

| Ветка | Статус | Назначение |
|-------|--------|------------|
| `main` | ✅ Актуальна | **Production** (основная) |
| `dev` | ✅ Актуальна | Development (разработка) |

---

## 🔧 Шаг 1: Сменить default branch на GitHub

**Важно:** Это нужно сделать вручную через веб-интерфейс GitHub.

1. Откройте репозиторий: https://github.com/zergius85/jira_report/settings/branches

2. Нажмите кнопку **"Default branch"** (справа от названия ветки)

3. Выберите **`main`** из выпадающего списка

4. Подтвердите смену:
   - Нажмите **"I understand, change the default branch"**

5. Проверьте, что `main` теперь отображается как default:
   ```
   🌳 main ← Default branch
   ```

---

## 🔒 Шаг 2: Добавить защиту ветки main (Branch Protection)

**Цель:** Запретить прямые пуши в `main`, требовать pull request.

1. Перейдите: https://github.com/zergius85/jira_report/settings/branches

2. Нажмите **"Add rule"** или **"Edit"** для `main`

3. Настройте правила:

   ### Обязательные настройки:
   - ✅ **Require a pull request before merging**
     - ✅ Require approvals (минимум 1 аппрув)
     - ✅ Dismiss stale pull request approvals when new commits are pushed
   
   ### Рекомендуемые настройки:
   - ✅ **Require status checks to pass before merging**
     - ✅ Require branches to be up to date before merging
   - ✅ **Include administrators** (применять ко всем, включая админов)
   - ✅ **Do not allow bypassing the above settings**
   - ✅ **Allow force pushes** — ❌ отключить!
   - ✅ **Allow deletions** — ❌ отключить!

4. Сохраните: **"Create"** или **"Save changes"**

---

## 🔄 Шаг 3: Обновить рабочий процесс

### Для разработки:

```bash
# Переключитесь на dev для новой функциональности
git checkout dev

# Создайте новую ветку для фичи
git checkout -b feature/new-feature

# После завершения:
git push origin feature/new-feature
```

### Для релиза:

```bash
# Создайте Pull Request на GitHub:
# feature/new-feature → dev

# После тестирования на dev:
git checkout dev
git pull origin dev

# Создайте Pull Request:
# dev → main

# После аппрува и мержа:
git checkout main
git pull origin main
git tag -a v1.2.0 -m "Release v1.2.0"
git push origin v1.2.0
```

---

## 📊 Шаг 4: Обновить CI/CD (если есть)

Если используете GitHub Actions или другой CI:

### `.github/workflows/deploy.yml`:

```yaml
on:
  push:
    branches:
      - main  # Было: dev

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
        with:
          ref: main  # Было: dev
      # ... остальной деплой
```

---

## 🎯 Шаг 5: Проверка

### Убедитесь, что всё работает:

1. **Проверьте default branch на GitHub:**
   ```bash
   git remote show origin
   # HEAD branch: main
   ```

2. **Проверьте защиту ветки:**
   - Попробуйте сделать `git push origin main` с локальными изменениями
   - Должна быть ошибка: "protected branch hook declined"

3. **Проверьте Pull Request:**
   - Создайте тестовую ветку
   - Запушьте
   - Создайте PR: `test-branch → main`
   - Убедитесь, что требуются статус-чеки и аппрувы

---

## 📝 Чек-лист

- [ ] Default branch изменён на `main` на GitHub
- [ ] Branch protection настроен для `main`
- [ ] CI/CD обновлён для `main`
- [ ] Команда уведомлена о новом процессе
- [ ] Документация обновлена (README, RECOMMENDATIONS)

---

## 🔗 Полезные ссылки

- [GitHub Branch Protection Rules](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/defining-the-mergeability-of-pull-requests/about-protected-branches)
- [GitHub Pull Requests](https://docs.github.com/en/pull-requests)
- [Git Flow Workflow](https://www.atlassian.com/git/tutorials/comparing-workflows/gitflow-workflow)

---

## ❓ Вопросы?

Если что-то непонятно или нужна помощь — обратитесь к документации GitHub или к тимлиду.
