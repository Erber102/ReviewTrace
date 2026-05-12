# Privacy

ReviewTrace runs entirely on your local machine. No data is uploaded to ReviewTrace servers.

## What may be sent to external services

When you run ReviewTrace, the following data may be sent to third-party API providers:

| Data | Destination |
|---|---|
| Research topic and search queries | OpenAlex, arXiv, Semantic Scholar |
| Paper titles, abstracts, and metadata | Your configured LLM provider (for screening and evidence extraction) |
| Screening criteria | Your configured LLM provider |
| Extracted evidence snippets | Your configured LLM provider (for taxonomy labelling) |

The data sent to paper retrieval APIs (OpenAlex, arXiv, Semantic Scholar) is governed by their respective terms of service and privacy policies.

The data sent to your LLM provider is governed by that provider's terms of service and data processing policies.

## Warning

Do not use ReviewTrace to process confidential, unpublished, embargoed, or otherwise sensitive materials unless you have reviewed and accepted the data handling policies of your configured retrieval and LLM providers.

## API keys

API keys are loaded from environment variables or your local `.env` file. They are never transmitted to ReviewTrace servers and are never logged.

**Do not commit `.env` to version control.** It is included in `.gitignore` by default.
