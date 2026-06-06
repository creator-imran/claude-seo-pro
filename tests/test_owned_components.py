#!/usr/bin/env python3
"""
Adversarial stress test for the Pro-owned components (knowledge / routing / connector /
onboarding). Tries to BREAK each one with edge + hostile inputs. Offline only — no
network, no Slack, no live runs. Exits non-zero if any assertion fails.

Runs in CI on every push (see .github/workflows/ci.yml) and locally:
    python tests/test_owned_components.py

Repo root is resolved RELATIVE to this file, so it works on any machine / CI runner.
"""
import sys, os, json, hmac, hashlib, time, importlib.util, shutil, tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS = {"pass": 0, "fail": 0, "fails": []}

def check(name, cond):
    if cond:
        RESULTS["pass"] += 1
    else:
        RESULTS["fail"] += 1
        RESULTS["fails"].append(name)
        print(f"  [FAIL] {name}")

def load(modpath, name):
    """Load a module by file path under a unique name (avoids sys.path collisions)."""
    d = os.path.dirname(modpath)
    if d not in sys.path:
        sys.path.insert(0, d)
    spec = importlib.util.spec_from_file_location(name, modpath)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m

K = os.path.join(REPO, "knowledge")
R = os.path.join(REPO, "routing")
C = os.path.join(REPO, "connector")
O = os.path.join(REPO, "onboarding")
for d in (K, R, C, O):
    sys.path.insert(0, d)
fsutil = load(os.path.join(K, "fsutil.py"), "k_fsutil")
store = load(os.path.join(K, "store.py"), "store")
cache = load(os.path.join(K, "cache.py"), "cache")
learn = load(os.path.join(K, "learn.py"), "learn")
router = load(os.path.join(R, "model_router.py"), "model_router")
cauth = load(os.path.join(C, "auth.py"), "auth")
ccmd = load(os.path.join(C, "commands.py"), "commands")
crun = load(os.path.join(C, "runner.py"), "runner")
providers = load(os.path.join(O, "providers.py"), "providers")
validate = load(os.path.join(O, "validate.py"), "validate")

print("=== KNOWLEDGE STORE: edge cases ===")
check("slugify url+path", fsutil.slugify("HTTPS://WWW.Example.COM/p?x=1") == "example-com")
check("slugify empty->unknown", fsutil.slugify("") == "unknown")
check("slugify junk->unknown", fsutil.slugify("...!!!") == "unknown")
ks = store.KnowledgeStore("stress-test.example")
try:
    ks.add_fact("")
    check("empty fact raises", False)
except ValueError:
    check("empty fact raises", True)
ks.supersede(["nonexistent-key"])
check("supersede nonexistent no-crash", True)
ks.add_fact("Unicode fact: cafe ee chinese \U0001f600", evidence="x", confidence="high", source="t")
check("unicode fact stored", any("Unicode" in f["text"] for f in ks.facts()))
ks.add_fact("Tagged market fact", evidence="x", confidence="high", tags=["mkt"])
check("facts_with_tag", len(ks.facts_with_tag("mkt")) == 1)
shutil.rmtree(fsutil.CLIENTS_ROOT / "stress-test-example", ignore_errors=True)

print("=== DATA CACHE: edge cases ===")
dc = cache.DataCache("stresstest")
check("get missing -> None", dc.get("op", {"a": 1}) is None)
dc.put("op", {"a": 1, "b": 2}, {"v": 1})
check("get hit", dc.get("op", {"a": 1, "b": 2})["data"]["v"] == 1)
check("key order-independent", dc.get("op", {"b": 2, "a": 1})["data"]["v"] == 1)
check("expired(max_age=0) -> None", dc.get("op", {"a": 1, "b": 2}, max_age_seconds=0) is None)
check("provenance present", dc.provenance("op", {"a": 1, "b": 2})["cached"] is True)
check("provenance missing -> None", dc.provenance("nope", {}) is None)
for f in (fsutil.cache_dir("stresstest")).glob("*.json"):
    f.unlink()

print("=== LEARN: guards (try to slip junk in) ===")
def lc(text, **kw):
    return learn.classify({"text": text, **kw})[0]
check("empty rejected", lc("") == "reject")
check("too-short rejected", lc("short") == "reject")
check("secret:password rejected", lc("the admin password is hunter2longenough") == "reject")
check("secret:token rejected", lc("set token=abcdef123456 in env now") == "reject")
check("secret:AIza rejected", lc("key AIza" + "B"*33 + " is live") == "reject")
check("secret:fc- rejected", lc("use fc-" + "a"*20 + " here") == "reject")
check("secret:hex32 rejected", lc("hash " + "a"*32 + " value") == "reject")
check("transient:score rejected", lc("the overall score is 61 right now") == "reject")
check("transient:today rejected", lc("the site ranks number one today here") == "reject")
check("transient:as-of rejected", lc("as of 2026-06 the traffic rose") == "reject")
check("durable+evidence ok", lc("Targets KSA as a secondary market clearly", evidence="pages") == "ok")
check("durable no-evidence downgrade", lc("Targets KSA as a secondary market clearly", confidence="high") == "downgrade")
res = learn.process("stress-learn.example", [], write=False)
check("empty batch no-crash", res["counts"]["added_or_would"] == 0)
shutil.rmtree(fsutil.CLIENTS_ROOT / "stress-learn-example", ignore_errors=True)

print("=== ROUTER: fallback + overrides ===")
router.POLICY_PATH = os.path.join(tempfile.gettempdir(), "stress-model-policy.json")
if os.path.exists(router.POLICY_PATH): os.remove(router.POLICY_PATH)
check("unknown agent -> reasoning", router.route(agent="seo-unknown")["tier"] == "reasoning")
check("unknown task -> fallback", router.route(task="weird")["tier"] == "reasoning")
check("known agent extraction", router.route(agent="seo-technical")["model"] == "claude-haiku-4-5")
e = router.estimate("extraction", 40000, 8000)
check("estimate saves vs opus", e["saved_usd"] > 0 and e["usd"] < e["usd_if_opus"])
check("opus estimate saves 0", router.estimate("synthesis", 1000, 1000)["saved_usd"] == 0.0)
router.save_policy({"force_model": "claude-sonnet-4-6"})
check("force_model full-id applied", router.route(agent="seo-technical")["model"] == "claude-sonnet-4-6")
router.save_policy({"tier_models": {"extraction": "claude-opus-4-8"}})
check("tier_models remap applied", router.route(agent="seo-technical")["model"] == "claude-opus-4-8")
if os.path.exists(router.POLICY_PATH): os.remove(router.POLICY_PATH)

print("=== CONNECTOR AUTH: rejection matrix ===")
secret = "stress-secret"
body = "command=%2Fseo&text=audit+https%3A%2F%2Fexample.com&user_id=U1&channel_id=C1&response_url=https%3A%2F%2Fh.test%2Fx"
ts = str(int(time.time()))
goodsig = "v0=" + hmac.new(secret.encode(), f"v0:{ts}:{body}".encode(), hashlib.sha256).hexdigest()
check("auth good", cauth.verify_slack_signature(secret, ts, body, goodsig)[0])
check("auth missing ts", not cauth.verify_slack_signature(secret, None, body, goodsig)[0])
check("auth non-int ts", not cauth.verify_slack_signature(secret, "abc", body, goodsig)[0])
check("auth future ts (out of window)", not cauth.verify_slack_signature(secret, str(int(time.time())+10000), body, goodsig)[0])
check("auth empty sig", not cauth.verify_slack_signature(secret, ts, body, "")[0])
check("authz deny-by-default", not cauth.is_authorized("U1", "C1", [], [])[0])
check("authz user ok", cauth.is_authorized("U1", "C9", ["U1"], [])[0])

print("=== CONNECTOR COMMANDS: parsing edge cases ===")
def pc(t, en=None):
    return ccmd.parse_command(t, enabled=en)
check("uppercase+spaces", pc("  AUDIT   https://x.com  ")[0]["action"] == "audit")
check("leading slash stripped", pc("/audit https://x.com")[0]["action"] == "audit")
check("no target error", pc("page")[1] is not None)
check("non-url for url-cmd error", pc("audit notaurl")[1] is not None)
check("keyword takes phrase", pc("keyword exhibition stand dubai")[0] is not None)
check("disabled command error", pc("audit https://x.com", en=["page"])[1] is not None)
check("unknown command error", pc("frobnicate x")[1] is not None)

print("=== CONNECTOR runner: pure builder ===")
p, _ = pc("audit https://example.com")
cmd = crun.build_cli_command(p, {"claude_bin": "claude", "model": "claude-opus-4-8", "permission_mode": "acceptEdits"})
check("builder has -p + prompt", "-p" in cmd and any("seo-audit" in x for x in cmd))
check("builder has model flag", "--model" in cmd and "claude-opus-4-8" in cmd)
check("dry_run no execution", crun.run(p, {"run_backend": "claude-cli"}, dry_run=True)["dry_run"] is True)

print("=== CONNECTOR handle_slash: full decision path (monkeypatched config) ===")
sb = load(os.path.join(C, "slack_bridge.py"), "slack_bridge")
sb.config.slack_creds = lambda: {"signing_secret": secret, "bot_token": ""}
sb.config.connector = lambda: {"enabled_commands": ["audit"], "allowed_users": ["U1"],
                               "allowed_channels": [], "run_backend": "claude-cli"}
hdr = {"X-Slack-Signature": goodsig, "X-Slack-Request-Timestamp": ts}
st, ack, job = sb.handle_slash(hdr, body)
check("handle: authed valid -> 200 + job", st == 200 and job is not None)
st2, ack2, job2 = sb.handle_slash({"X-Slack-Signature": goodsig[:-1]+("1" if goodsig[-1]!="1" else "2"), "X-Slack-Request-Timestamp": ts}, body)
check("handle: bad sig -> 401 + no job", st2 == 401 and job2 is None)
body_u9 = body.replace("user_id=U1", "user_id=U9")
sig_u9 = "v0=" + hmac.new(secret.encode(), f"v0:{ts}:{body_u9}".encode(), hashlib.sha256).hexdigest()
st3, ack3, job3 = sb.handle_slash({"X-Slack-Signature": sig_u9, "X-Slack-Request-Timestamp": ts}, body_u9)
check("handle: unauthorized -> 200 + no job", st3 == 200 and job3 is None and "authoriz" in ack3["text"].lower())
body_bad = body.replace("text=audit+https%3A%2F%2Fexample.com", "text=frobnicate+x")
sig_bad = "v0=" + hmac.new(secret.encode(), f"v0:{ts}:{body_bad}".encode(), hashlib.sha256).hexdigest()
st4, ack4, job4 = sb.handle_slash({"X-Slack-Signature": sig_bad, "X-Slack-Request-Timestamp": ts}, body_bad)
check("handle: unknown cmd -> 200 + no job", st4 == 200 and job4 is None)

print("=== ONBOARDING: providers/validators integrity ===")
ids = providers.ids()
check("all providers have a validator", all(i in validate.VALIDATORS for i in ids))
check("all secret providers have fields", all(providers.by_id(i)["fields"] for i in ids))
for i in ids:
    pr = providers.by_id(i)
    if pr.get("mcp"):
        try:
            entry = pr["mcp"]["builder"]({})
            check(f"mcp builder {i} returns command", "command" in entry)
        except Exception:
            check(f"mcp builder {i} no-crash", False)
check("slack provider config_file=slack", providers.config_name(providers.by_id("slack")) == "slack")
check("google-oauth config_file=google-api", providers.config_name(providers.by_id("google-oauth")) == "google-api")
for i in ids:
    r = validate.validate(i, {})
    check(f"validator {i} returns dict w/ ok", isinstance(r, dict) and "ok" in r)

print(f"\n==== STRESS TEST: {RESULTS['pass']} passed, {RESULTS['fail']} failed ====")
if RESULTS["fails"]:
    print("FAILURES:", RESULTS["fails"])
sys.exit(1 if RESULTS["fail"] else 0)
