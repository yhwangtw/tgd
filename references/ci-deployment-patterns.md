# CI and Deployment Patterns

These are optional, illustrative recipes. They do not define gates, thresholds, or failure behavior. Apply the normative workflow in the parent `tgd-release-ci` skill and substitute the project's actual commands and platform from `$TGD_DIR/CONTEXT.md`.

## Basic GitHub Actions Pipeline

```yaml
# .github/workflows/ci.yml
name: CI

on:
  pull_request:
    branches: [main]
  push:
    branches: [main]

jobs:
  quality:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: '22'
          cache: 'npm'
      - run: npm ci
      - name: Lint
        run: npm run lint
      - name: Type check
        run: npx tsc --noEmit
      - name: Test
        run: npm test -- --coverage
      - name: Build
        run: npm run build
      - name: Security audit
        run: npm audit --audit-level=high
```

## Database Integration Job

```yaml
integration:
  runs-on: ubuntu-latest
  services:
    postgres:
      image: postgres:16
      env:
        POSTGRES_DB: testdb
        POSTGRES_USER: ci_user
        POSTGRES_PASSWORD: ${{ secrets.CI_DB_PASSWORD }}
      ports: [5432:5432]
      options: >-
        --health-cmd pg_isready
        --health-interval 10s
        --health-timeout 5s
        --health-retries 5
  steps:
    - uses: actions/checkout@v4
    - uses: actions/setup-node@v4
      with: { node-version: '22', cache: 'npm' }
    - run: npm ci
    - name: Run migrations
      run: npx prisma migrate deploy
      env:
        DATABASE_URL: postgresql://ci_user:${{ secrets.CI_DB_PASSWORD }}@localhost:5432/testdb
    - name: Integration tests
      run: npm run test:integration
      env:
        DATABASE_URL: postgresql://ci_user:${{ secrets.CI_DB_PASSWORD }}@localhost:5432/testdb
```

## E2E Job

```yaml
e2e:
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v4
    - uses: actions/setup-node@v4
      with: { node-version: '22', cache: 'npm' }
    - run: npm ci
    - run: npx playwright install --with-deps chromium
    - run: npm run build
    - run: npx playwright test
    - uses: actions/upload-artifact@v4
      if: failure()
      with:
        name: playwright-report
        path: playwright-report/
```

## Preview and Rollback Jobs

```yaml
deploy-preview:
  runs-on: ubuntu-latest
  if: github.event_name == 'pull_request'
  steps:
    - uses: actions/checkout@v4
    - run: npx vercel --token=${{ secrets.VERCEL_TOKEN }}
```

```yaml
name: Rollback
on:
  workflow_dispatch:
    inputs:
      version:
        description: 'Vercel deployment ID to roll back to (dpl_...)'
        required: true
jobs:
  rollback:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: '22'
          cache: 'npm'
      - name: Install locked dependencies
        run: npm ci
      - name: Roll back deployment
        env:
          VERSION: ${{ inputs.version }}
          VERCEL_TOKEN: ${{ secrets.VERCEL_TOKEN }}
        shell: bash
        run: |
          if [[ ! "$VERSION" =~ ^dpl_[A-Za-z0-9]{20,64}$ ]]; then
            echo "Invalid Vercel deployment ID" >&2
            exit 2
          fi
          npx --no-install vercel rollback --token="$VERCEL_TOKEN" -- "$VERSION"
```

## Dependency Updates

```yaml
# .github/dependabot.yml
version: 2
updates:
  - package-ecosystem: npm
    directory: /
    schedule:
      interval: weekly
    open-pull-requests-limit: 5
```

## Parallel Jobs

This abbreviated pattern applies the same checkout, runtime setup, install, and command shape to independent jobs:

```yaml
jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: '22', cache: 'npm' }
      - run: npm ci
      - run: npm run lint
  typecheck:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: '22', cache: 'npm' }
      - run: npm ci
      - run: npx tsc --noEmit
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: '22', cache: 'npm' }
      - run: npm ci
      - run: npm test -- --coverage
```
