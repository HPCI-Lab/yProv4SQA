# SQAaaS 

SQAaaS is a cloud-based, open-science service that automatically checks your research software for quality best practices (testing, licensing, documentation, etc.) after every commit and awards an open-badge report you can download as JSON.

## How to obtain assessment reports

### CI route (every push) - Example usage - Recommended

In most cases, one would use the action in order to run the SQAaaS quality assessment for the repository and branch that triggered the action. To this end, you just need to use the action in your workflow as follows:

```yaml
uses: eosc-synergy/sqaaas-assessment-action@v2
```

However, if required, the action can be used to assess alternative combinations of repositories and branches. Here, you
would need to use the optional inputs `repo` and `branch`, such as in:

```yaml
uses: eosc-synergy/sqaaas-assessment-action@v2
with:
  repo: 'https://github.com/eosc-synergy/sqaaas-assessment-action'
  branch: 'main'
```

### Quick GUI route

1. Visit https://sqaaas.eosc-synergy.eu  (Use this URL to retrieve the repository’s current quality assessment)
2. Sign in with whichever account you prefer, open “Quality Assessment & Awarding,” and paste the repo link into the “Repository URL” box under the “Source Code” tab.
3. After completion click “Start Source Code Assessment”

For full input/output details, custom steps, status badges and advanced options  please visit the official site: https://docs.sqaaas.eosc-synergy.eu/