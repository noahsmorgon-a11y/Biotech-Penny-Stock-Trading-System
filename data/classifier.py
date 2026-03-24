"""Classify news articles into catalyst categories using Claude Haiku."""

import json

import anthropic

import config

SYSTEM_PROMPT = f"""You are a biotech stock catalyst analyst. Analyze news articles about a biotech stock and classify the primary catalyst that caused its price movement.

## Catalyst Categories (use ONLY these exact strings):
{chr(10).join(f'- {ct}' for ct in config.CATALYST_TYPES)}

Category definitions:
- FDA_APPROVAL: Drug/device received FDA approval, positive advisory committee vote, or PDUFA date result
- FDA_REJECTION: Complete Response Letter, refusal to file, or negative advisory committee vote
- CLINICAL_TRIAL_POSITIVE: Trial met primary endpoints, showed positive efficacy/safety data
- CLINICAL_TRIAL_NEGATIVE: Trial failed endpoints, safety concerns, or was discontinued
- EARNINGS: Quarterly results (beat or miss), revenue reports, financial updates
- PARTNERSHIP_OR_MA: Licensing deal, collaboration, acquisition, merger, or buyout
- SHORT_SQUEEZE: Price driven by short covering with no fundamental catalyst
- ANALYST_RATING: Analyst upgrade, downgrade, or significant price target change
- ADVERSE_EVENT: Serious adverse events, FDA clinical hold, patient death in trial
- OTHER: Clear catalyst that doesn't fit above categories
- UNKNOWN: Cannot determine catalyst from available information

## Output Format:
Return ONLY valid JSON (no markdown, no explanation):
{{
  "catalyst_type": "one of the categories above",
  "confidence": 0.85,
  "summary": "One sentence describing exactly what happened (max 150 chars)"
}}

## Rules:
- confidence is 0.0-1.0 (1.0 = certain)
- For SHORT_SQUEEZE: only classify if article explicitly mentions short interest or short covering
- If no articles are relevant to a biotech catalyst, use UNKNOWN
- summary must be specific and factual"""


def classify_mover_event(
    ticker: str,
    company_name: str,
    pct_change: float,
    articles: list[dict],
    dry_run: bool = False,
) -> dict:
    """Classify a mover event by analyzing its news articles with Claude.

    Returns dict with keys: catalyst_type, catalyst_confidence, news_headline, news_summary
    """
    default = {
        "catalyst_type": "UNKNOWN",
        "catalyst_confidence": 0.0,
        "news_headline": "",
        "news_summary": "",
    }

    if not articles:
        return default

    if dry_run or not config.ANTHROPIC_API_KEY:
        return {
            **default,
            "news_headline": articles[0].get("headline", "") if articles else "",
        }

    # Build user message with articles
    article_text = ""
    for i, a in enumerate(articles[:config.CLAUDE_BATCH_SIZE]):
        article_text += f"\n--- ARTICLE {i + 1} ---\n"
        article_text += f"Headline: {a.get('headline', 'N/A')}\n"
        article_text += f"Summary: {a.get('summary', 'N/A')}\n"
        article_text += f"Source: {a.get('source', 'N/A')}\n"

    user_msg = (
        f"Stock: {ticker} ({company_name})\n"
        f"Price movement: {pct_change:+.1f}% \n\n"
        f"Analyze these news articles and classify the primary catalyst "
        f"for this stock's price movement:\n{article_text}"
    )

    try:
        client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
        response = client.messages.create(
            model=config.CLAUDE_MODEL,
            max_tokens=256,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_msg}],
        )

        response_text = response.content[0].text.strip()
        result = _parse_response(response_text)

        # Pick the best headline to associate with this classification
        best_headline = articles[0].get("headline", "") if articles else ""

        return {
            "catalyst_type": result.get("catalyst_type", "UNKNOWN"),
            "catalyst_confidence": round(result.get("confidence", 0.0), 2),
            "news_headline": best_headline,
            "news_summary": result.get("summary", ""),
        }

    except Exception as e:
        print(f"  Claude error for {ticker}: {e}")
        return {
            **default,
            "news_headline": articles[0].get("headline", "") if articles else "",
        }


def _parse_response(text: str) -> dict:
    """Parse Claude's JSON response, handling common issues."""
    # Strip markdown code fences if present
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines)

    try:
        result = json.loads(text)
    except json.JSONDecodeError:
        # Try to extract JSON from the response
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                result = json.loads(text[start:end])
            except json.JSONDecodeError:
                return {"catalyst_type": "UNKNOWN", "confidence": 0.0, "summary": ""}
        else:
            return {"catalyst_type": "UNKNOWN", "confidence": 0.0, "summary": ""}

    # Validate catalyst_type
    if result.get("catalyst_type") not in config.CATALYST_TYPES:
        result["catalyst_type"] = "UNKNOWN"

    return result
