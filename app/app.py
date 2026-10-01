"""One engine, every source: a live demo of Exasol federating Snowflake, S3 and Qdrant Cloud, with in-database ML.

Run:  ./app/run.sh   ->  http://localhost:8510   (settings come from .env, see README.md)
"""
import base64
import html as _h
import json
import urllib.request
from pathlib import Path

import streamlit as st

import db
from theme import CSS

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from demo.config import get, vec_table  # noqa: E402

st.set_page_config(page_title="One engine, every source — Exasol", layout="wide",
                   initial_sidebar_state="collapsed")
HERE = Path(__file__).resolve().parent
SQLDIR = Path(__file__).resolve().parent.parent / "setup" / "sql"
VEC_TABLE = vec_table()
REGION = get("REGION_LABEL", "AWS")
ss = st.session_state


def html(fragment: str, target=st) -> None:
    """Collapse blank lines so Streamlit's markdown pass cannot end the HTML block."""
    target.markdown("\n".join(l for l in fragment.splitlines() if l.strip()), unsafe_allow_html=True)


html(CSS)
html("""<style>
.block-container { padding-top:1rem !important; }
.dgm { border-radius:22px; border:1px solid var(--edge); background:#fff; box-shadow:var(--shadow); padding:.5rem .6rem .2rem; }
.dgm svg { display:block; width:100%; height:auto; font-family:Figtree,sans-serif; }
.dgm .zone { fill:#F6F9FC; stroke:#DFE5EE; stroke-dasharray:6 5; }
.dgm .zlabel { font-size:12px; font-weight:800; letter-spacing:.14em; fill:#66748A; }
.dgm .node { transition:opacity .3s; }
.dgm .node rect { fill:#fff; stroke:#DFE5EE; stroke-width:1.5; }
.dgm .node .nt { font-size:19px; font-weight:800; fill:#0B1B34; }
.dgm .node .ns { font-size:13px; fill:#66748A; }
.dgm .node.exa rect { fill:#F2FBF9; stroke:#9ED9CE; stroke-width:2; }
.dgm .node.on rect { stroke:#1FA08B; stroke-width:3.5; }
.dgm .edge { stroke:#B9C5D3; stroke-width:3; fill:none; transition:opacity .3s; }
.dgm .edge.on { stroke:#1FA08B; stroke-width:5; stroke-dasharray:12 8; animation:flow .8s linear infinite; }
@keyframes flow { to { stroke-dashoffset:-40; } }
.dgm .dim { opacity:.28; }
.dgm .node.via rect { stroke:#1FA08B; stroke-width:2; stroke-dasharray:7 5; }
.dgm .node.via { opacity:.75; }
.dgm .edge.via { stroke:#1FA08B; stroke-width:3; stroke-dasharray:4 6; opacity:.7; }
.dgm .pill.via rect { fill:#7FB8AE; }
.dgm .node.user rect { fill:#081226; stroke:#081226; } .dgm .node.user .nt { fill:#fff; } .dgm .node.user .ns { fill:#B8C6DA; }
.dgm .node.vsband rect { fill:#E3F5F1; stroke:#9ED9CE; stroke-width:2; }
.dgm .node.vsband.on rect { stroke:#1FA08B; stroke-width:3; }
.dgm .vt { font-size:16px; font-weight:800; fill:#12796A; } .dgm .vs2 { font-size:12px; fill:#4A5464; }
.dgm .udf rect { fill:#fff; stroke:#9ED9CE; stroke-width:1.5; stroke-dasharray:5 4; }
.dgm .udf.on rect { stroke:#1FA08B; stroke-width:3; stroke-dasharray:none; } .dgm .udf.dim { opacity:.35; }
.dgm .ut { font-size:14px; font-weight:800; fill:#0B1B34; } .dgm .us { font-size:11.5px; fill:#66748A; }
.ov-band { margin:1.6rem 0 .5rem; } .ov-k { text-transform:uppercase; letter-spacing:.14em; font-size:.7rem; font-weight:800; color:var(--teal-ink); }
.ov-h { font-size:1.45rem; font-weight:800; letter-spacing:-.02em; color:var(--ink2); margin:.15rem 0 .2rem; }
.ov-s { font-size:.98rem; color:var(--muted); line-height:1.55; max-width:62rem; }
.cmp2 { display:grid; grid-template-columns:1fr 1fr; gap:1rem; margin:.7rem 0 .4rem; }
.cc { border-radius:18px; border:1px solid var(--edge); background:#fff; padding:1rem 1.2rem; }
.cc.bad { border-left:5px solid var(--no); } .cc.good { border-left:5px solid var(--teal); }
.cc .k { text-transform:uppercase; letter-spacing:.12em; font-size:.66rem; font-weight:800; }
.cc.bad .k { color:var(--no); } .cc.good .k { color:var(--teal-ink); }
.cc .t { font-weight:800; font-size:1.15rem; margin:.2rem 0 .5rem; }
.cc ul { margin:0 0 0 1.1rem; padding:0; } .cc li { margin:.28rem 0; line-height:1.5; color:var(--muted); }
.steps4 { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:.6rem; margin:.7rem 0 .5rem; }
.st4 { border-radius:16px; border:1px solid var(--edge); background:#fff; padding:.8rem .9rem; position:relative; }
.st4 .n { font-size:.66rem; font-weight:800; letter-spacing:.12em; color:var(--teal-ink); text-transform:uppercase; }
.st4 .t { font-weight:800; font-size:1rem; margin:.15rem 0 .3rem; } .st4 .d { font-size:.85rem; color:var(--muted); line-height:1.45; }
.st4.exa { background:#F2FBF9; border-color:#CDEBE4; }
.live { border-radius:14px; background:#F6F9FC; border:1px solid var(--edge); padding:.6rem .9rem; font-size:.88rem; color:var(--ink2); margin:.3rem 0; }
.live b { color:var(--teal-ink); }
.tok { display:grid; grid-template-columns:1fr auto 1fr auto 1fr; gap:.7rem; align-items:center; margin:.7rem 0 .4rem; }
.tk2 { border-radius:18px; border:1px solid var(--edge); background:#fff; padding:.9rem 1.1rem; }
.tk2 .v { font-size:2rem; font-weight:900; color:var(--ink2); font-variant-numeric:tabular-nums; line-height:1.1; }
.tk2 .k { font-size:.85rem; color:var(--muted); margin-top:.2rem; line-height:1.4; }
.tk2.bad .v { color:var(--no); } .tk2.good { background:#E3F5F1; border-color:#CDEBE4; } .tk2.good .v { color:var(--teal-ink); }
.tk2.navy { background:linear-gradient(135deg,#081226 0%,#12796A 100%); border:0; } .tk2.navy .v, .tk2.navy .k { color:#fff; }
.tka { font-size:1.6rem; color:var(--faint); }
.trace { border-radius:16px; border:1px solid var(--edge); background:#fff; padding:.4rem .2rem; margin:.5rem 0; }
.tr { display:grid; grid-template-columns:2.2rem minmax(0,1.5fr) minmax(0,2fr) 6rem 7rem; gap:.6rem; align-items:center;
  padding:.5rem .8rem; border-bottom:1px solid #EEF2F7; font-size:.88rem; }
.tr:last-child { border-bottom:0; } .tr.h { font-size:.62rem; font-weight:800; letter-spacing:.1em; text-transform:uppercase; color:var(--faint); }
.tr .ic { width:26px; height:26px; border-radius:50%; display:flex; align-items:center; justify-content:center; font-size:.7rem; font-weight:800; }
.tr .ic.llm { background:#EEF0FF; color:#4B4FD8; } .tr .ic.sql { background:#E3F5F1; color:var(--teal-ink); }
.tr .nm { font-weight:800; } .tr .ds { color:var(--muted); font-size:.82rem; } .tr .num { text-align:right; font-variant-numeric:tabular-nums; font-weight:700; }
.tr.tot { background:#F6F9FC; font-weight:800; }
@media (max-width:1000px) { .cmp2, .steps4 { grid-template-columns:1fr; } .tok { grid-template-columns:1fr; } .tka { display:none; } }
.ov-s:empty { display:none; }
.pipe { display:flex; align-items:stretch; gap:.4rem; margin:.8rem 0 .4rem; }
.pp { flex:1; border-radius:18px; border:1px solid var(--edge); background:#fff; padding:1rem .8rem; text-align:center; box-shadow:0 8px 22px rgba(8,18,38,.05); }
.pp.exa { background:linear-gradient(180deg,#E3F5F1 0%,#fff 100%); border-color:#9ED9CE; }
.pp-ic { width:54px; height:54px; border-radius:50%; margin:0 auto .5rem; display:flex; align-items:center; justify-content:center;
  background:#EEF2F7; color:var(--ink2); } .pp.exa .pp-ic { background:#12796A; color:#fff; }
.pp-t { font-weight:900; font-size:1.05rem; color:var(--ink2); } .pp-d { font-size:.8rem; color:var(--muted); margin-top:.1rem; }
.pp-tg { display:inline-block; margin-top:.45rem; font-family:'JetBrains Mono',monospace; font-size:.66rem; color:#0076AD; background:#E2F4FF; border-radius:999px; padding:.1rem .5rem; }
.pp-ar { display:flex; align-items:center; color:#9FB0C4; font-size:1.4rem; font-weight:800; }
.pp-loop { display:flex; align-items:center; gap:1rem; flex-wrap:wrap; font-size:.88rem; font-weight:700; color:var(--teal-ink); margin:.3rem 0 .2rem .3rem; }
.pp-chip { font-size:.76rem; font-weight:800; color:#fff; background:var(--navy); border-radius:999px; padding:.25rem .8rem; }
.big-x { color:var(--teal-ink); }
.tbars { border-radius:20px; border:1px solid var(--edge); background:#fff; padding:1.1rem 1.2rem .9rem; margin:.7rem 0 .3rem; }
.tb-row { display:grid; grid-template-columns:15rem 1fr 7rem; gap:1rem; align-items:center; margin:.55rem 0 1.1rem; }
.tb-l { font-weight:800; font-size:.95rem; color:var(--ink2); line-height:1.25; } .tb-l span { display:block; font-weight:600; font-size:.76rem; color:var(--faint); }
.tb-tr { position:relative; height:34px; border-radius:10px; background:#F1F4F9; }
.tb-f { height:100%; border-radius:10px; } .tb-f.bad { background:linear-gradient(90deg,#FF7A85,#C8102E); } .tb-f.good { background:#1FA08B; min-width:4px; }
.tb-ctx { position:absolute; top:-10px; bottom:-10px; border-left:3px dashed #081226; }
.tb-ctx span { position:absolute; top:-1.35rem; left:-.2rem; white-space:nowrap; font-size:.7rem; font-weight:800; color:#081226; }
.tb-pin { position:absolute; top:50%; transform:translateY(-50%); margin-left:.6rem; font-size:.8rem; font-weight:800; color:var(--teal-ink); white-space:nowrap; }
.tb-v { font-size:1.5rem; font-weight:900; text-align:right; font-variant-numeric:tabular-nums; } .tb-v.bad { color:#C8102E; } .tb-v.good { color:var(--teal-ink); }
.lf { border-radius:20px; border:1px solid var(--edge); background:#fff; padding:.9rem 1.2rem .7rem; margin:.7rem 0 .2rem; }
.lf-hd { display:flex; align-items:center; gap:.6rem; font-size:.85rem; font-weight:800; color:var(--ink2); margin-bottom:.7rem; }
.lf-dot { width:10px; height:10px; border-radius:50%; background:#1FA08B; }
.lf-tot { margin-left:auto; font-size:.8rem; color:#fff; background:var(--navy); border-radius:999px; padding:.2rem .75rem; }
.lf-row { display:grid; grid-template-columns:13rem 1fr; gap:1rem; align-items:center; margin:.45rem 0; }
.lf-n { font-weight:800; font-size:.92rem; color:var(--ink2); display:flex; align-items:center; gap:.5rem; }
.lf-b { font-size:.62rem; font-weight:900; letter-spacing:.06em; border-radius:6px; padding:.12rem .4rem; }
.lf-b.llm { background:#EEF0FF; color:#4B4FD8; } .lf-b.sql { background:#E3F5F1; color:var(--teal-ink); }
.lf-tr { position:relative; height:30px; background:repeating-linear-gradient(90deg,#F6F9FC 0 24.9%,#EEF2F7 25% 25.2%); border-radius:8px; }
.lf-bar { position:absolute; top:3px; bottom:3px; border-radius:7px; display:flex; align-items:center; padding:0 .6rem; overflow:visible; }
.lf-bar.llm { background:#6B6FE8; } .lf-bar.sql { background:#1FA08B; }
.lf-bar span { color:#fff; font-size:.74rem; font-weight:800; white-space:nowrap; }
.lf-ax { display:flex; justify-content:space-between; margin-left:14rem; font-size:.68rem; color:var(--faint); margin-top:.2rem; }
.tiles { display:grid; grid-template-columns:repeat(6,minmax(0,1fr)); gap:.7rem; margin:.6rem 0 .4rem; }
.tl { border-radius:18px; border:1px solid var(--edge); background:#fff; padding:1.1rem .8rem; text-align:center; box-shadow:0 8px 22px rgba(8,18,38,.05); }
.tl-ic { width:58px; height:58px; border-radius:18px; margin:0 auto .6rem; display:flex; align-items:center; justify-content:center;
  background:linear-gradient(135deg,#081226 0%,#12796A 100%); color:#fff; }
.tl-t { font-weight:900; font-size:1rem; color:var(--ink2); line-height:1.25; } .tl-f { font-size:.74rem; font-weight:800; color:var(--teal-ink); margin-top:.35rem; }
@media (max-width:1100px) { .tiles { grid-template-columns:repeat(3,minmax(0,1fr)); } .pipe { flex-wrap:wrap; } .pp-ar { display:none; }
  .tb-row { grid-template-columns:1fr; } .lf-row { grid-template-columns:1fr; } .lf-ax { margin-left:0; } }
.dgm .sem rect { fill:#081226; stroke:#081226; } .dgm .sem .st1 { font-size:15px; font-weight:800; fill:#fff; }
.dgm .sem .st2 { font-size:12px; fill:#B8E6DC; }
.fail3 { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)) auto minmax(0,1.15fr); gap:.6rem; align-items:stretch; margin:.7rem 0 .4rem; }
.f3 { border-radius:16px; border:1px solid #F3C2C8; border-top:4px solid #C8102E; background:#fff; padding:.8rem .9rem; }
.f3.good { border:0; background:linear-gradient(135deg,#081226 0%,#12796A 100%); }
.f3-k { font-size:.62rem; font-weight:800; letter-spacing:.12em; text-transform:uppercase; color:#C8102E; }
.f3-t { font-weight:900; font-size:1.05rem; color:var(--ink2); margin:.15rem 0 .2rem; } .f3-d { font-size:.84rem; color:var(--muted); }
.f3.good .f3-k { color:#7FE3D0; } .f3.good .f3-t { color:#fff; font-size:1.2rem; } .f3.good .f3-d { color:#D6F3EC; }
.f3-ar { display:flex; align-items:center; font-size:1.6rem; color:var(--faint); font-weight:800; }
.layers { display:grid; gap:.45rem; margin-top:.4rem; }
.ly { display:grid; grid-template-columns:9.5rem 1fr; gap:.8rem; align-items:center; border-radius:14px; border:1px solid var(--edge); background:#fff; padding:.75rem 1rem; }
.ly.exa { background:#F2FBF9; border-color:#CDEBE4; } .ly.dark { background:#081226; border-color:#081226; }
.ly-n { font-weight:900; font-size:.95rem; color:var(--ink2); } .ly-t { font-size:.9rem; color:var(--muted); }
.ly.dark .ly-n { color:#fff; } .ly.dark .ly-t { color:#B8E6DC; }
.fan { border-radius:20px; border:1px solid var(--edge); background:#fff; padding:1rem 1.2rem .8rem; margin:.7rem 0 .3rem; }
.fn-row { display:grid; grid-template-columns:12rem 1fr; gap:1rem; align-items:center; margin:.5rem 0; }
.fn-l { font-weight:800; font-size:.95rem; color:var(--ink2); line-height:1.25; } .fn-l span { display:block; font-weight:600; font-size:.76rem; color:var(--faint); }
.fn-tr { height:38px; border-radius:10px; background:#F1F4F9; }
.fn-f { height:100%; border-radius:10px; display:flex; align-items:center; justify-content:flex-end; padding-right:.8rem; }
.fn-f span { color:#fff; font-weight:900; font-size:1.05rem; font-variant-numeric:tabular-nums; }
.fn-f.bad { background:linear-gradient(90deg,#FF7A85,#C8102E); } .fn-f.good { background:#1FA08B; }
.fn-foot { display:flex; align-items:center; gap:.8rem; flex-wrap:wrap; font-size:.88rem; color:var(--muted); margin-top:.6rem; }
.fn-foot b { color:var(--ink2); }
.fn-x { font-size:1.05rem; font-weight:900; color:#fff; background:#C8102E; border-radius:999px; padding:.2rem .8rem; }
.path5 { display:grid; grid-template-columns:repeat(5,minmax(0,1fr)); gap:.6rem; margin:.7rem 0 .4rem; position:relative; }
.p5 { border-radius:18px; border:1px solid var(--edge); background:#fff; padding:.9rem .8rem; text-align:center; }
.p5-n { width:34px; height:34px; border-radius:50%; margin:0 auto .4rem; display:flex; align-items:center; justify-content:center;
  font-weight:900; background:#EEF2F7; color:var(--ink2); }
.p5-t { font-weight:900; font-size:1.05rem; color:var(--ink2); } .p5-d { font-size:.8rem; color:var(--muted); margin-top:.1rem; }
.p5-s { display:inline-block; margin-top:.45rem; font-size:.66rem; font-weight:800; letter-spacing:.06em; text-transform:uppercase;
  border-radius:999px; padding:.12rem .55rem; background:#F1F4F9; color:var(--faint); }
.p5.done { background:#F2FBF9; border-color:#9ED9CE; } .p5.done .p5-n { background:#1FA08B; color:#fff; } .p5.done .p5-s { background:#1FA08B; color:#fff; }
.p5.sv .p5-n { background:#081226; color:#fff; } .p5.sv .p5-s { background:#081226; color:#fff; }
@media (max-width:1100px) { .fail3 { grid-template-columns:1fr; } .f3-ar { display:none; } .path5 { grid-template-columns:repeat(2,minmax(0,1fr)); }
  .fn-row, .ly { grid-template-columns:1fr; } }

/* ---- lighter palette: no heavy black blocks; Semantic Views gets its own soft indigo ---- */
.dgm .node.user rect { fill:#E2F4FF !important; stroke:#7CC8F0 !important; stroke-width:2 !important; }
.dgm .node.user .nt { fill:#0B1B34 !important; } .dgm .node.user .ns { fill:#0076AD !important; }
.dgm .node.user.on rect { stroke:#0076AD !important; stroke-width:3 !important; }
.dgm .sem rect { fill:#EEF0FF !important; stroke:#9EA3F0 !important; stroke-width:2 !important; }
.dgm .sem .st1 { fill:#3B3FB8 !important; } .dgm .sem .st2 { fill:#5B5F88 !important; }
.ly.dark { background:#EEF0FF !important; border-color:#C9CCF7 !important; }
.ly.dark .ly-n { color:#3B3FB8 !important; } .ly.dark .ly-t { color:#5B5F88 !important; }
.f3.good { background:linear-gradient(135deg,#E3F5F1 0%,#F2FBF9 100%) !important; border:2px solid #1FA08B !important; }
.f3.good .f3-k { color:#12796A !important; } .f3.good .f3-t { color:#0B1B34 !important; } .f3.good .f3-d { color:#12796A !important; }
.p5.sv { background:#F5F6FF; border-color:#C9CCF7; }
.p5.sv .p5-n { background:#6B6FE8 !important; } .p5.sv .p5-s { background:#6B6FE8 !important; }
.pp-chip, .lf-tot { background:#12796A !important; }
.dgm .pill rect { fill:#3A4A63; }
.dgm .vialbl { font-size:12px; font-weight:800; fill:#12796A; font-style:italic; }
.dgm .pill rect { fill:#081226; } .dgm .pill text { font-size:13px; font-weight:800; fill:#fff; }
.dgm .pill.on rect { fill:#1FA08B; }
.dgm .flowlbl { font-size:12.5px; font-weight:800; fill:#12796A; }
.dgm .flowlbl.back { fill:#0076AD; }
.qk { text-transform:uppercase; letter-spacing:.14em; font-size:.7rem; font-weight:800; color:var(--teal-ink); margin:.1rem 0 .4rem; }
.ans { border-radius:20px; border:1px solid var(--edge); background:#fff; box-shadow:var(--shadow); padding:1rem 1.15rem; margin-top:.6rem; }
.ans .q { font-size:1.25rem; font-weight:800; line-height:1.3; color:var(--ink2); margin-bottom:.1rem; }
.ans .src { font-size:.85rem; color:var(--muted); }
.big3 { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:.55rem; margin:.8rem 0 .7rem; }
.b3 { border-radius:14px; background:#F6F9FC; padding:.6rem .8rem; }
.b3 .v { font-size:1.6rem; font-weight:800; color:var(--ink2); line-height:1.1; font-variant-numeric:tabular-nums; }
.b3 .k { font-size:.78rem; color:var(--muted); margin-top:.15rem; line-height:1.3; }
.b3.hl { background:#E3F5F1; } .b3.hl .v { color:var(--teal-ink); }
.did { margin:.2rem 0 0; }
.did .k { text-transform:uppercase; letter-spacing:.12em; font-size:.64rem; font-weight:800; color:var(--teal-ink); margin-bottom:.3rem; }
.did ul { margin:0 0 0 1.1rem; padding:0; } .did li { margin:.25rem 0; font-size:.95rem; line-height:1.45; color:var(--ink); }
.cached { border-radius:10px; background:#FDF3F4; color:var(--no); font-size:.8rem; font-weight:700; padding:.35rem .6rem; margin-top:.5rem; }
.tk { border-radius:12px; border:1px solid var(--edge); padding:.45rem .7rem; margin-bottom:.35rem; font-size:.88rem; line-height:1.4; }
.tk.churn { border-left:4px solid var(--no); }
.tk .tag { font-size:.6rem; font-weight:800; text-transform:uppercase; letter-spacing:.08em; border-radius:999px;
  padding:.05rem .45rem; background:#F1F4F9; color:var(--muted); margin-right:.35rem; }
.tk.churn .tag { background:var(--no); color:#fff; }
.cu { display:grid; grid-template-columns:minmax(0,1fr) 5.5rem; gap:.6rem; align-items:center; border-bottom:1px solid #EEF2F7; padding:.4rem 0; }
.cu:last-child { border-bottom:0; }
.cu .nm { font-weight:800; font-size:.92rem; } .cu .mt { font-size:.78rem; color:var(--muted); font-style:italic; line-height:1.35; }
.cu .v { text-align:right; font-weight:800; font-variant-numeric:tabular-nums; }
.hint { font-size:.95rem; color:var(--muted); line-height:1.55; }
.punch { border-radius:18px; margin:1rem 0 .4rem; padding:1.1rem 1.3rem;
  background:linear-gradient(135deg,#081226 0%,#10203F 55%,#12796A 100%); box-shadow:0 14px 34px rgba(8,18,38,.22); }
.punch .pt { color:#fff; font-size:1.75rem; font-weight:900; letter-spacing:-.02em; line-height:1.15; }
.punch .pv { color:#fff; font-size:1.15rem; font-weight:700; margin-top:.35rem; opacity:.92; }
.punch .pv::first-line { }
.punch .ps { color:#7FE3D0; font-size:.82rem; font-weight:800; letter-spacing:.14em; text-transform:uppercase; margin-top:.45rem; }
.why6 { display:grid; grid-template-columns:repeat(6,minmax(0,1fr)); gap:.6rem; margin:1.4rem 0 .4rem; }
.w6 { border-radius:14px; background:#fff; border:1px solid var(--edge); padding:.7rem .8rem; }
.w6 .t { font-weight:800; font-size:.9rem; line-height:1.3; } .w6 .d { font-size:.8rem; color:var(--muted); margin-top:.25rem; line-height:1.4; }
.w6 .f { font-size:.72rem; font-weight:800; color:var(--teal-ink); margin-top:.35rem; }
div[data-testid="stVerticalBlock"] .stButton > button { justify-content:flex-start !important; text-align:left !important; }
.st-key-qbtns .stButton > button { min-height:2.8rem !important; font-size:.95rem !important; }
.st-key-qbtns .stButton > button { justify-content:flex-start !important; padding-left:1rem !important; }
.st-key-qbtns .stButton > button > div, .st-key-qbtns .stButton > button [data-testid="stMarkdownContainer"] {
  justify-content:flex-start !important; text-align:left !important; width:100%; }
.st-key-qbtns .stButton > button p { text-align:left !important; width:100%; margin:0; }
.dmap { display:grid; grid-template-columns:repeat(5,minmax(0,1fr)); gap:.6rem; margin:0 0 1rem; }
.dm { border-radius:16px; border:1px solid var(--edge); background:#fff; padding:.7rem .9rem; }
.dm.exa { background:#F2FBF9; border-color:#CDEBE4; }
.dm .dk { text-transform:uppercase; letter-spacing:.12em; font-size:.64rem; font-weight:800; color:var(--teal-ink); }
.dm .ds { font-weight:800; font-size:1.1rem; margin:.1rem 0 .15rem; } .dm .ds span { font-weight:600; font-size:.82rem; color:var(--faint); }
.dm .dt { font-family:'JetBrains Mono',monospace; font-size:.74rem; color:#0076AD; }
.dm .dd { font-size:.8rem; color:var(--muted); margin-top:.2rem; line-height:1.35; }
.cmpk { margin:1.6rem 0 .4rem; }
@media (max-width:1300px) { .why6 { grid-template-columns:repeat(3,minmax(0,1fr)); } .dmap { grid-template-columns:repeat(2,minmax(0,1fr)); } }
</style>""")


def _logo() -> str:
    b64 = base64.b64encode((HERE / "assets" / "exasol_logo_dark.svg").read_bytes()).decode()
    return (f'<img src="data:image/svg+xml;base64,{b64}" alt="Exasol" width="104" height="26" '
            f'style="height:26px;width:auto;max-width:104px;display:block;"/>')


# ------------------------------------------------------------------ SQL (shown only to engineers)
Q_SF = """SELECT NATION, ORDERS, ROUND(REVENUE / 1e6, 1) AS REVENUE_M
FROM  (SELECT n.N_NAME AS NATION, COUNT(*) AS ORDERS, SUM(o.O_TOTALPRICE) AS REVENUE
       FROM   DEMO_SNOWFLAKE.ORDERS   o
       JOIN   DEMO_SNOWFLAKE.CUSTOMER c ON c.C_CUSTKEY   = o.O_CUSTKEY
       JOIN   DEMO_SNOWFLAKE.NATION   n ON n.N_NATIONKEY = c.C_NATIONKEY
       GROUP  BY n.N_NAME)
ORDER BY REVENUE_M DESC
LIMIT 5"""
Q_S3 = """SELECT L_SHIPMODE AS SHIP_MODE, COUNT(*) AS LINES,
       ROUND(AVG(L_DAYS_LATE), 1) AS AVG_DAYS_LATE
FROM   DEMO_FEDERATED.S3_LINEITEM      -- a view over IMPORT FROM PARQUET on S3
GROUP  BY L_SHIPMODE
ORDER  BY AVG_DAYS_LATE DESC"""
QD_TEXT = "goods smashed during shipping"
Q_ACC = "CREATE OR REPLACE TABLE " + (SQLDIR / "20_accelerate.sql").read_text().split(
    "CREATE OR REPLACE TABLE", 1)[1].strip().rstrip(";")
Q_FAST = """-- question 1 again, now on the copy inside Exasol (built once from Snowflake + S3)
SELECT NATION, SUM(ORDERS) AS ORDERS, ROUND(SUM(LIFETIME_REVENUE) / 1e6, 1) AS REVENUE_M
FROM   DEMO_ACCEL.CUSTOMER_360
GROUP  BY NATION ORDER BY REVENUE_M DESC LIMIT 5"""
HERO = "-- Q6" + (SQLDIR / "50_questions.sql").read_text().replace("{VEC_TABLE}", VEC_TABLE).split("-- Q6", 1)[1].strip().rstrip(";")
Q_ML_SCORE = """SELECT COUNT(*) AS TICKETS_SCORED,
       SUM(CASE WHEN DEMO_AI.CHURN_RISK(TICKET_TEXT) >= 0.5 THEN 1 ELSE 0 END) AS FLAGGED
FROM   DEMO_DATA.SUPPORT_TICKETS"""
Q_ML = """WITH scored AS (                                   -- the model runs here, on every ticket
  SELECT C_CUSTKEY, TICKET_TEXT, DEMO_AI.CHURN_RISK(TICKET_TEXT) AS RISK
  FROM   DEMO_DATA.SUPPORT_TICKETS),
per_customer AS (
  SELECT C_CUSTKEY, SUM(CASE WHEN RISK >= 0.5 THEN 1 ELSE 0 END) AS RISKY_TICKETS,
         MAX(RISK) AS MAX_RISK, MAX(CASE WHEN RISK >= 0.5 THEN TICKET_TEXT END) AS EXAMPLE
  FROM scored GROUP BY C_CUSTKEY)
SELECT c.C_NAME AS CUSTOMER, c.NATION, p.RISKY_TICKETS, ROUND(100 * p.MAX_RISK) AS RISK_PCT,
       ROUND(c.OPEN_ORDER_VALUE / 1e3, 0) AS OPEN_ORDERS_K, p.EXAMPLE
FROM   per_customer p
JOIN   DEMO_ACCEL.CUSTOMER_360 c ON c.C_CUSTKEY = p.C_CUSTKEY   -- revenue from Snowflake + S3, accelerated
WHERE  p.RISKY_TICKETS > 0
ORDER  BY p.RISKY_TICKETS DESC, c.OPEN_ORDER_VALUE DESC
LIMIT  5"""
Q_ML_TRAIN = """-- training runs inside Exasol too: a SET UDF receives the training rows and fits scikit-learn
SELECT DEMO_AI.TRAIN_CHURN_MODEL(TICKET_TEXT, CHURN_INTENT)
FROM   DEMO_DATA.SUPPORT_TICKETS
WHERE  MOD(TICKET_ID, 5) <> 0          -- 80% train; the other 20% is the unseen test set"""
Q_ML_META = """SELECT r.VERSION, r.TRAINED_AT, r.N_TRAIN, r.ALGORITHM, m.N_TEST, m.ACCURACY, m.PRECISION_, m.RECALL
FROM DEMO_AI.MODEL_REGISTRY r JOIN DEMO_AI.MODEL_METRICS m ON m.VERSION = r.VERSION ORDER BY r.VERSION DESC LIMIT 1"""


def q_qd(text):
    return f"""SELECT v."SCORE" AS RANK_SCORE, t.TICKET_ID, t.CATEGORY, t.CHURN_INTENT, t.TICKET_TEXT
FROM  (SELECT "ID", "SCORE" FROM {VEC_TABLE}
       WHERE "QUERY" = '{text.replace("'", "''")}' LIMIT 4) v
JOIN   DEMO_DATA.SUPPORT_TICKETS t ON t.TICKET_ID = CAST(v."ID" AS DECIMAL(9,0))
ORDER  BY v."SCORE" DESC"""


# ------------------------------------------------------------------ the five questions
QUESTIONS = {
    "sf": dict(n=1, ask="Which countries bring the most revenue?", src="Snowflake, read live",
               nodes={"cloud", "snow"}, edges={"C"}, go="the question", back="25 rows",
               did=["Sent the whole question (join and totals) to Snowflake, in Snowflake's own SQL.",
                    "Snowflake did the work; only the 25 country totals came back.",
                    "Nothing was copied, so the answer is always current."]),
    "s3": dict(n=2, ask="Which shipping modes run late?", src="Parquet files on Amazon S3, read in place",
               nodes={"cloud", "s3"}, edges={"D"}, go="read files", back="6 M rows",
               did=["Read seven Parquet files straight from the S3 bucket, with a read-only key.",
                    "Scanned six million shipment lines in parallel, in seconds.",
                    "No load job: the files stay in the lake, owned by the lake."]),
    "qd": dict(n=3, ask="Find complaints about damaged goods", src="Qdrant Cloud vector store, searched by meaning",
               nodes={"cloud", "qdrant"}, edges={"A"}, go="your words", back="best matches",
               did=["Sent the words to Qdrant Cloud, which turned them into a vector itself and returned the nearest tickets.",
                    "Qdrant's matches came back as rows of an ordinary table.",
                    "Those rows join to any other data with plain SQL (question 6)."]),
    "acc": dict(n=4, ask="Same revenue question, after moving the data into Exasol", src="Question 1 again, on the copy in Exasol's in-memory engine: same numbers, a fraction of the time",
                nodes={"cloud"}, edges=set(), go="", back="",
                did=["One statement copied the Snowflake orders (joined with S3 shipments) into an Exasol table.",
                     "The same question returns the same numbers as live Snowflake, so the move can be proven, table by table.",
                     "Every model, dashboard and agent now reads it in milliseconds."]),
    "ml": dict(n=5, ask="Which customers does our ML model flag as likely to leave?", src="Python UDF running scikit-learn, inside Exasol",
               nodes={"cloud"}, edges={"E"}, go="", back="",
               did=["The model was trained inside Exasol by a Python UDF (scikit-learn) and deployed to BucketFS.",
                    "A Python UDF scored all 5,000 tickets in parallel, where the data lives: nothing was exported.",
                    "To rank who matters most, the same SQL added each flagged customer's open orders from the accelerated customer table."]),
    "all": dict(n=6, ask="Which unhappy customers put the most revenue at risk?", src="Qdrant Cloud and the ML model live, plus Snowflake and S3 data through the accelerated customer table",
                nodes={"cloud", "qdrant"}, edges={"A", "E"}, via={"snow", "s3"}, via_edges={"C", "D"}, go="", back="",
                punch=("No pipeline was built for this question.", "Just virtual schemas and a UDF: Qdrant Cloud searched live, the model scored in the database.", "Four sources &middot; one SQL statement &middot; zero copies"),
                did=["Qdrant Cloud found 300 tickets that sound like a customer about to leave.",
                     "The ML model (Python UDF) confirmed which of them really signal churn.",
                     "Exasol added open orders (Snowflake) and late shipments (S3) from the table built in question 4, in the same SQL."]),
}


def run_question(k):
    if k == "sf":
        return {"main": db.run("cloud", Q_SF, key="sf"), "push": explain("cloud", Q_SF, "sf")}
    if k == "s3":
        return {"main": db.run("cloud", Q_S3, key="s3b")}
    if k == "qd":
        text = ss.get("qd_text", QD_TEXT)
        return {"main": db.run("cloud", q_qd(text), key="vec4"), "text": text}
    if k == "acc":
        return {"main": db.run("cloud", Q_FAST, key="acc")}
    if k == "ml":
        return {"main": db.run("cloud", Q_ML, key="ml"), "score": db.run("cloud", Q_ML_SCORE, key="ml_score"),
                "meta": db.run("cloud", Q_ML_META, key="ml_meta")}
    return {"main": db.run("cloud", HERO, key="hero"), "push": explain("cloud", HERO, "all")}


def explain(which, sql, key):
    res = db.run(which, "EXPLAIN VIRTUAL " + sql, key=f"explain_{key}")
    return [str(list(r.values())[1]) for r in res["rows"]]


def pretty(pushdown):
    if "STATEMENT '" in pushdown:
        inner = pushdown.split("STATEMENT '", 1)[1].rstrip("'").replace("''", "'")
        for kw in (" FROM ", " INNER JOIN ", " GROUP BY "):
            inner = inner.replace(kw, "\n" + kw.strip() + " ")
        return inner
    return pushdown


# ------------------------------------------------------------------ the diagram
def diagram(active):
    """User -> Exasol (with the UDF) -> virtual schemas -> Snowflake, S3, Qdrant Cloud. Lights the path a question takes."""
    q = QUESTIONS.get(active)
    on_n, on_e = (set(q["nodes"]), set(q["edges"])) if q else (set(), set())
    if active == "acc":
        on_e, on_n = {"C", "D"}, {"cloud", "snow", "s3"}
    via_n, via_e = (q.get("via", set()), q.get("via_edges", set())) if q else (set(), set())
    if q:
        on_n |= {"user"}
        on_e |= {"U"}
        if on_e & {"A", "C", "D"} or via_e:
            on_e |= {"V"}
            on_n |= {"vs"}

    def cn(k, extra=""):
        c = "node" + extra
        if q:
            c += " on" if k in on_n else " via" if k in via_n else " dim"
        return c

    def ce(k):
        return "edge" + ((" on" if k in on_e else " via" if k in via_e else " dim") if q else "")

    def pill(k, x, y):
        c = "pill" + ((" on" if k in on_e else " via" if k in via_e else " dim") if q else "")
        return (f'<g class="{c}"><rect x="{x - 16}" y="{y - 15}" width="32" height="30" rx="15"/>'
                f'<text x="{x}" y="{y + 5}" text-anchor="middle">{k}</text></g>')

    lbl = ""
    if q and q.get("go"):
        for e, x in (("C", 110), ("D", 310), ("A", 510)):
            if e in on_e:
                lbl += (f'<text class="flowlbl" x="{x - 22}" y="{452}" text-anchor="end">&darr; {q["go"]}</text>'
                        f'<text class="flowlbl back" x="{x + 22}" y="{474}" text-anchor="start">&uarr; {q["back"]}</text>')
    udf_on = active in ("ml", "all")
    nat_on = active in ("acc", "ml", "all")
    udf_cls = "udf" + ((" on" if udf_on else " dim") if q else "")
    nat_cls = "udf" + ((" on" if nat_on else " dim") if q else "")
    return f'''<div class="dgm"><svg viewBox="0 0 620 630" role="img" aria-label="Architecture">
  <line class="{ce("U")}" x1="310" y1="72" x2="310" y2="112"/>
  <line class="{ce("V")}" x1="310" y1="338" x2="310" y2="364"/>
  <line class="{ce("C")}" x1="110" y1="420" x2="110" y2="500"/>
  <line class="{ce("D")}" x1="310" y1="420" x2="310" y2="500"/>
  <line class="{ce("A")}" x1="510" y1="420" x2="510" y2="500"/>
  <g class="{cn("user", " user")}"><rect x="160" y="14" width="300" height="58" rx="29"/><text class="nt" x="310" y="40" text-anchor="middle">User</text><text class="ns" x="310" y="60" text-anchor="middle">analyst · notebook · BI tool · AI agent</text></g>
  <g class="{cn("cloud", " exa")}"><rect x="40" y="112" width="540" height="226" rx="18"/><text class="nt" x="62" y="144">Exasol</text><text class="ns" x="138" y="144">SaaS · one governed SQL endpoint</text></g>
  <g class="sem"><rect x="62" y="158" width="496" height="70" rx="12"/><text class="st1" x="82" y="186">Semantic Views · the certified business contract</text><text class="st2" x="82" y="208">metrics, grain and identity defined once; ill-posed questions are refused</text></g>
  <g class="{nat_cls}"><rect x="62" y="240" width="240" height="80" rx="12"/><text class="ut" x="80" y="268">Native tables</text><text class="us" x="80" y="288">the accelerated working set</text><text class="us" x="80" y="306">CUSTOMER_360 + tickets</text></g>
  <g class="{udf_cls}"><rect x="318" y="240" width="240" height="80" rx="12"/><text class="ut" x="336" y="268">Python UDF</text><text class="us" x="336" y="288">the ML model, scikit-learn</text><text class="us" x="336" y="306">scores rows in parallel</text></g>
  <g class="{cn("vs", " vsband")}"><rect x="30" y="364" width="560" height="56" rx="14"/><text class="vt" x="310" y="388" text-anchor="middle">Virtual schemas &amp; connectors</text><text class="vs2" x="310" y="407" text-anchor="middle">SQL is translated and pushed to each source, only answers come back</text></g>
  <g class="{cn("snow")}"><rect x="20" y="500" width="180" height="110" rx="16"/><text class="nt" x="38" y="536">Snowflake</text><text class="ns" x="38" y="559">customers + orders</text><text class="ns" x="38" y="579">150 k + 1.5 M rows</text></g>
  <g class="{cn("s3")}"><rect x="220" y="500" width="180" height="110" rx="16"/><text class="nt" x="238" y="536">Amazon S3</text><text class="ns" x="238" y="559">shipments, Parquet</text><text class="ns" x="238" y="579">6 M lines, 7 files</text></g>
  <g class="{cn("qdrant")}"><rect x="420" y="500" width="180" height="110" rx="16"/><text class="nt" x="438" y="536">Qdrant Cloud</text><text class="ns" x="438" y="559">5,000 support tickets</text><text class="ns" x="438" y="579">embeds text itself</text></g>
  {pill("C", 110, 460)}{pill("D", 310, 460)}{pill("A", 510, 460)}{pill("E", 558, 240)}
  {lbl}
  {'<text class="vialbl" x="210" y="444" text-anchor="middle">built in question 4</text>' if via_e else ""}
</svg></div>'''


LEGEND = {"A": "Qdrant Cloud: a Python virtual-schema adapter sends your search text over https; Qdrant embeds it and returns the nearest tickets as rows",
          "C": "Snowflake: a JDBC virtual schema pushes the SQL down, Snowflake does the work",
          "D": "Amazon S3: Exasol reads the Parquet files in place, no load step",
          "E": "Python UDF inside Exasol: an ML model from BucketFS scores every row in parallel, next to the data"}


# ------------------------------------------------------------------ answer visuals
def bars(rows, label_col, val_col, fmt, unit=""):
    top = max((r[val_col] or 0) for r in rows) or 1
    out = '<div class="hbars">'
    for r in rows:
        v = r[val_col] or 0
        out += (f'<div class="hb"><div class="hb-l">{_h.escape(str(r[label_col]).title())}</div>'
                f'<div class="hb-t"><div class="hb-f" style="width:{max(4, 100 * v / top):.0f}%"></div></div>'
                f'<div class="hb-v">{fmt.format(v)}{unit}</div></div>')
    return out + "</div>"


def big3(items):
    return '<div class="big3">' + "".join(
        f'<div class="b3{" hl" if hl else ""}"><div class="v">{v}</div><div class="k">{k}</div></div>' for v, k, hl in items) + "</div>"


def answer(k, out):
    res = out["main"]
    rows = res["rows"]
    if k == "sf":
        nums = [("1.5 M", "orders stayed in Snowflake", False), ("25", "rows came back", True), (f"{res['secs']:.0f} s", "live, end to end", False)]
        vis = bars(rows, "NATION", "REVENUE_M", "${:,.0f}", " M")
    elif k == "s3":
        nums = [("6.0 M", "rows read in place", False), ("0", "rows loaded first", True), (f"{res['secs']:.1f} s", "live, end to end", False)]
        vis = bars(rows, "SHIP_MODE", "AVG_DAYS_LATE", "{:.1f}", " days")
    elif k == "qd":
        nums = [("5,000", "tickets searched", False), ("by meaning", "not by keyword", True), (f"{res['secs']:.1f} s", "live, end to end", False)]
        vis = ""
        for t in rows:
            churn = t.get("CHURN_INTENT") == 1
            tag = "churn risk" if churn else str(t.get("CATEGORY", "")).replace("_", " ")
            vis += f'<div class="tk{" churn" if churn else ""}"><span class="tag">{_h.escape(tag)}</span>{_h.escape(str(t["TICKET_TEXT"]))}</div>'
    elif k == "acc":
        sf = ss.get("done_sf", {}).get("main")
        if not sf:
            f = HERE / "cache" / "sf.json"
            sf = json.loads(f.read_text()) if f.exists() else None
        live = (sf or {}).get("secs") or 11.0
        same = bool(sf) and {(r["NATION"], round(float(r["REVENUE_M"]), 1)) for r in sf["rows"]} == \
            {(r["NATION"], round(float(r["REVENUE_M"]), 1)) for r in rows}
        nums = [(f"{res['secs']:.2f} s", f"in Exasol, against {live:.0f} s live from Snowflake", True),
                ("identical" if same else "check", "numbers to question 1, country by country" if same else "compare with question 1", False),
                (f"{live / max(res['secs'], .01):,.0f}&times;", "faster after the move", False)]
        vis = bars(rows, "NATION", "REVENUE_M", "${:,.0f}", " M")
    elif k == "ml":
        sc = out["score"]["rows"][0] if out["score"]["rows"] else {}
        meta = out["meta"]["rows"][0] if out["meta"]["rows"] else {}
        acc = 100 * float(meta.get("ACCURACY") or 0)
        nums = [(f"{sc.get('TICKETS_SCORED', 0):,}", f"tickets scored inside Exasol in {out['score']['secs']:.1f} s", True),
                (f"{sc.get('FLAGGED', 0):,}", "flagged as churn risk", False),
                (f"{acc:.0f}%", f"accuracy on {int(meta.get('N_TEST') or 0):,} tickets the model never saw", False)]
        vis = "".join(f'<div class="cu"><div><div class="nm">{_h.escape(str(r["CUSTOMER"]))} &middot; {_h.escape(str(r["NATION"]).title())}'
                      f' &middot; {r["RISKY_TICKETS"]} risky tickets</div>'
                      f'<div class="mt">&ldquo;{_h.escape(str(r["EXAMPLE"])[:120])}&hellip;&rdquo;</div></div>'
                      f'<div class="v">{r["RISK_PCT"]:.0f}%<div class="mt" style="font-style:normal">${r["OPEN_ORDERS_K"]:,.0f}K open</div></div></div>'
                      for r in rows)
        vis += ('<div class="hint" style="margin-top:.5rem;font-size:.82rem">Accuracy is this high because the synthetic tickets '
                'express churn in a few fixed phrases. Real tickets will score lower; the point here is the workflow, '
                'trained, deployed and scored inside the database.</div>')
    else:
        risk = sum(r.get("OPEN_ORDERS_K") or 0 for r in rows) / 1000
        nums = [("4", "sources of data, one query", False), (f"${risk:,.1f} M", "open orders at risk", True), (f"{res['secs']:.1f} s", "live, end to end", False)]
        vis = "".join(f'<div class="cu"><div><div class="nm">{_h.escape(str(r["CUSTOMER"]))} &middot; {_h.escape(str(r["NATION"]).title())}</div>'
                      f'<div class="mt">&ldquo;{_h.escape(str(r["SAMPLE_TICKET"])[:120])}&hellip;&rdquo;</div></div>'
                      f'<div class="v">${r["OPEN_ORDERS_K"]:,.0f}K</div></div>' for r in rows[:5])
    return nums, vis


# ------------------------------------------------------------------ page
@st.cache_data(ttl=20, show_spinner=False)
def health():
    h = {"cloud": db.ping("cloud")}
    try:
        req = urllib.request.Request(get("QDRANT_URL").rstrip("/") + "/collections/" + get("QDRANT_COLLECTION", "support_tickets"),
                                     headers={"api-key": get("QDRANT_API_KEY")})
        with urllib.request.urlopen(req, timeout=5) as r:
            h["qdrant"] = json.load(r)["result"]["points_count"] is not None
    except Exception:  # noqa: BLE001
        h["qdrant"] = False
    return h


h = health()
pill = lambda ok, t: f'<span class="hs-pill{"" if ok else " down"}">{t}</span>'  # noqa: E731
html(f'<div class="pagehead">{_logo()}<span class="ph-t">One engine, every source &middot; live demo</span></div>')
html(f'''<div class="hero-slim"><div class="hs-t">Ask any question, <em>wherever the data lives</em>
  <span>Snowflake, S3 and Qdrant Cloud, all on AWS, answered by one Exasol endpoint. Nothing copied first.</span></div>
  <div class="hs-m">{pill(h["cloud"], "Exasol cloud")}{pill(h["cloud"], "Snowflake")}
  {pill(h["cloud"], "S3")}{pill(h["qdrant"], "Qdrant Cloud")}</div></div>''')

tab_over, tab_demo = st.tabs(["1 · Overview", "2 · Live demo"])

with tab_demo:
    DATA = [("Who buys", "Snowflake", "the warehouse", "CUSTOMER 150 k rows · ORDERS 1.5 M rows",
             "Tables in Snowflake, read through a virtual schema"),
            ("What shipped", "Amazon S3", "the data lake", "LINEITEM 6 M shipment lines",
             "7 Parquet files (123 MB) in a bucket, read in place"),
            ("What they say", "Qdrant Cloud", "the vector store", "5,000 support tickets",
             "Hosted on AWS; Qdrant Cloud creates the vectors itself"),
            ("What it predicts", "Python UDF", "the ML model", "DEMO_AI.CHURN_RISK · churn v1",
             "scikit-learn model trained and run inside Exasol, stored in BucketFS"),
            ("Joined and fast", "Exasol", "the one engine", "CUSTOMER_360: 100 k customers",
             "Exasol SaaS: built from Snowflake + S3 in one statement; tickets stored here")]
    html('<div class="qk" style="margin-top:.2rem">What data lives where</div><div class="dmap">' + "".join(
        f'<div class="dm{" exa" if sys == "Exasol" else ""}"><div class="dk">{k}</div><div class="ds">{sys} <span>{role}</span></div>'
        f'<div class="dt">{tables}</div><div class="dd">{d}</div></div>' for k, sys, role, tables, d in DATA) + "</div>")

    active = ss.get("active")
    left, right = st.columns([1.05, 1], gap="large")

    with right:
        html('<div class="qk">Ask a question</div>')
        with st.container(key="qbtns"):
            for k, q in QUESTIONS.items():
                if st.button(f'{q["n"]}  ·  {q["ask"]}', key=f"q_{k}", use_container_width=True,
                             type="primary" if k == active else "secondary"):
                    ss["active"], ss["pending"] = k, True
                    st.rerun()
        if active == "qd":
            ss["qd_text"] = st.text_input("Search text (try your own words)", value=ss.get("qd_text", QD_TEXT))

        if active and ss.get("pending"):
            with st.spinner(f"Asking: {QUESTIONS[active]['ask']}"):
                ss[f"done_{active}"] = run_question(active)
            ss["pending"] = False
            st.rerun()

        if not active:
            html('<div class="ans"><div class="q">Pick a question</div><div class="hint">Each one is answered live. '
                 'Watch the diagram: it lights up the systems the question touches, and shows what travels between them. '
                 'The question goes out; only the answer comes back.</div></div>')
        elif ss.get(f"done_{active}"):
            q, out = QUESTIONS[active], ss[f"done_{active}"]
            nums, vis = answer(active, out)
            cached = "" if out["main"]["live"] else f'<div class="cached">Live source unavailable: showing the last good run.</div>'
            html(f'''<div class="ans"><div class="q">{q["ask"]}</div><div class="src">{q["src"]}</div>
                 {big3(nums)}{vis}{cached}
                 {(f'<div class="punch"><div class="pt">{q["punch"][0]}</div><div class="pv">{q["punch"][1]}</div>'
                   f'<div class="ps">{q["punch"][2]}</div></div>') if q.get("punch") else ""}
                 <div class="did" style="margin-top:.8rem"><div class="k">What Exasol did</div><ul>{"".join(f"<li>{d}</li>" for d in q["did"])}</ul></div></div>''')
            with st.expander("For engineers: the SQL, and what each source received"):
                sql = {"sf": Q_SF, "s3": Q_S3, "qd": q_qd(out.get("text", QD_TEXT)), "acc": Q_FAST, "all": HERO, "ml": Q_ML}[active]
                st.caption("The SQL you write in Exasol")
                st.code(sql.strip(), language="sql", wrap_lines=True)
                for p in out.get("push", []):
                    st.caption("Exasol cloud received (only the columns it needs)" if "FROM EXA" in p
                               else "Snowflake received" if "FROM JDBC" in p else "Qdrant returned its matches as rows")
                    st.code(pretty(p)[:1500], language="sql", wrap_lines=True)
                if active == "s3":
                    st.caption("S3 received: GET requests for the seven Parquet files, signed with a read-only key")
                if active == "qd":
                    st.caption("Behind the WHERE clause: a Python adapter sends the text over https to Qdrant Cloud, which embeds it and returns the nearest tickets")
                if active == "ml":
                    st.caption("Training, also inside Exasol")
                    st.code(Q_ML_TRAIN, language="sql", wrap_lines=True)
                    st.caption("The scoring UDF: Python, loaded once from BucketFS, then applied to every row in parallel")
                    st.code((SQLDIR / "40_ml_udfs.sql").read_text().split("-- Score:", 1)[1].strip(), language="python", wrap_lines=True)
                    meta = out["meta"]["rows"][0] if out["meta"]["rows"] else {}
                    st.caption(f"Model registry: churn v{meta.get('VERSION')}, trained {meta.get('TRAINED_AT')} on "
                               f"{meta.get('N_TRAIN')} tickets, {meta.get('ALGORITHM')}")
                if active == "acc":
                    st.caption("Built once with this statement (about 45 s):")
                    st.code(Q_ACC, language="sql", wrap_lines=True)
                    if st.button("Rebuild it now", key="rebuild"):
                        with st.spinner("Joining Snowflake orders with S3 shipments into Exasol…"):
                            r = db.run("cloud", Q_ACC, key="acc_build")
                        st.success(f"Rebuilt {r['rows'][0].get('ROWS_WRITTEN', 0):,} customers in {r['secs']:.0f} s" if r["live"]
                                   else f"Rebuild failed: {r['error']}")

    with left:
        html(diagram(active))
        q = QUESTIONS.get(active)
        edges = sorted({"C", "D"} if active == "acc" else ((q["edges"] | q.get("via_edges", set())) if q else set()))
        if edges:
            html("".join(f'<div class="hint" style="margin-top:.45rem"><b>{e}</b> &middot; {LEGEND[e]}</div>' for e in edges))
        elif not q:
            html("".join(f'<div class="hint" style="margin-top:.35rem"><b>{e}</b> &middot; {t}</div>' for e, t in LEGEND.items()))

# ------------------------------------------------------------------ tab 1: overview
Q_FANOUT = """SELECT
  (SELECT ROUND(SUM(c.OPEN_ORDER_VALUE) / 1e6, 1) FROM DEMO_DATA.SUPPORT_TICKETS t
     JOIN DEMO_ACCEL.CUSTOMER_360 c ON c.C_CUSTKEY = t.C_CUSTKEY) AS NAIVE_M,
  (SELECT ROUND(SUM(c.OPEN_ORDER_VALUE) / 1e6, 1) FROM DEMO_ACCEL.CUSTOMER_360 c
     WHERE c.C_CUSTKEY IN (SELECT C_CUSTKEY FROM DEMO_DATA.SUPPORT_TICKETS)) AS CORRECT_M,
  (SELECT COUNT(*) FROM DEMO_DATA.SUPPORT_TICKETS t JOIN DEMO_ACCEL.CUSTOMER_360 c ON c.C_CUSTKEY = t.C_CUSTKEY) AS JOINED_ROWS,
  (SELECT COUNT(DISTINCT t.C_CUSTKEY) FROM DEMO_DATA.SUPPORT_TICKETS t
     JOIN DEMO_ACCEL.CUSTOMER_360 c ON c.C_CUSTKEY = t.C_CUSTKEY) AS CUSTOMERS
FROM DUAL"""
Q_TOKENS = """SELECT (SELECT COUNT(*) FROM DEMO_DATA.SUPPORT_TICKETS) AS TICKETS,
       (SELECT ROUND(SUM(LENGTH(TICKET_TEXT)) / 4) FROM DEMO_DATA.SUPPORT_TICKETS) AS TICKET_TOKENS,
       (SELECT COUNT(*) FROM DEMO_ACCEL.CUSTOMER_360) AS CUSTOMERS,
       (SELECT ROUND(SUM(LENGTH(C_NAME || ',' || NATION || ',' || SEGMENT || ',' || OPEN_ORDER_VALUE || ','
                                || LIFETIME_REVENUE || ',' || PCT_LATE || ',' || AVG_DAYS_LATE)) / 4)
        FROM DEMO_ACCEL.CUSTOMER_360) AS CUSTOMER_TOKENS"""


@st.cache_data(ttl=600, show_spinner=False)
def token_budget():
    """Rough LLM token counts (about 4 characters per token), measured on the real tables."""
    r = db.run("cloud", Q_TOKENS, key="tokens")
    raw = r["rows"][0] if r["rows"] else {}
    hero = ss.get("done_all", {}).get("main")
    if not hero:
        f = HERE / "cache" / "hero.json"
        hero = json.loads(f.read_text()) if f.exists() else {"rows": [], "secs": 0}
    answer_tokens = max(1, round(len(json.dumps(hero["rows"], default=str)) / 4))
    return raw, answer_tokens, hero


with tab_over:
    html('''<div class="ov-band"><div class="ov-k">From federation to data fusion</div>
      <div class="ov-h">Enterprise data is distributed. AI needs one place to work.</div>
      <div class="ov-s">Start live with federation, add a certified semantic contract, accelerate only what proves worth it.</div></div>''')
    html('''<div class="fail3">
      <div class="f3"><div class="f3-k">Breaks down</div><div class="f3-t">Tool per system</div><div class="f3-d">The agent becomes the join engine</div></div>
      <div class="f3"><div class="f3-k">Breaks down</div><div class="f3-t">Copy everything first</div><div class="f3-d">Pipelines before any question</div></div>
      <div class="f3"><div class="f3-k">Breaks down</div><div class="f3-t">Raw text-to-SQL</div><div class="f3-d">Joins that run, and multiply</div></div>
      <div class="f3-ar">&rarr;</div>
      <div class="f3 good"><div class="f3-k">With Exasol</div><div class="f3-t">One data plane</div><div class="f3-d">Federate &middot; certify meaning &middot; accelerate</div></div></div>''')

    c1, c2 = st.columns([1, 1.1], gap="large")
    with c1:
        html('<div class="ov-band"><div class="ov-k">How it connects</div><div class="ov-h">One path for every question</div></div>')
        html(diagram(None))
    with c2:
        html('''<div class="ov-band"><div class="ov-k">Reading the diagram</div><div class="ov-h">Meaning first, then source, then execution</div></div>
          <div class="layers">
          <div class="ly"><div class="ly-n">User</div><div class="ly-t">One endpoint, any tool</div></div>
          <div class="ly dark"><div class="ly-n">Semantic Views</div><div class="ly-t">What the question means, and whether it is answerable</div></div>
          <div class="ly exa"><div class="ly-n">Exasol engine</div><div class="ly-t">Joins, native tables, Python UDFs</div></div>
          <div class="ly exa"><div class="ly-n">Virtual schemas</div><div class="ly-t">Push the work to each source</div></div>
          <div class="ly"><div class="ly-n">Sources</div><div class="ly-t">Stay where they are, owned by their teams</div></div></div>''')

    # ---- wrong but plausible: the fan-out the semantic layer refuses
    fan = db.run("cloud", Q_FANOUT, key="fanout")
    fr = fan["rows"][0] if fan["rows"] else {}
    naive, right = float(fr.get("NAIVE_M") or 0), float(fr.get("CORRECT_M") or 0)
    if naive and right:
        html(f'''<div class="ov-band"><div class="ov-k">Why a semantic contract</div>
          <div class="ov-h">Wrong but plausible is worse than an error</div>
          <div class="ov-s">"Open orders held by customers who complained", measured live on this demo's data.</div></div>
          <div class="fan">
            <div class="fn-row"><div class="fn-l">Natural join<span>the SQL runs fine</span></div>
              <div class="fn-tr"><div class="fn-f bad" style="width:100%"><span>${naive / 1000:,.2f} B</span></div></div></div>
            <div class="fn-row"><div class="fn-l">Correct answer<span>one row per customer</span></div>
              <div class="fn-tr"><div class="fn-f good" style="width:{100 * right / naive:.1f}%"><span>${right / 1000:,.2f} B</span></div></div></div>
            <div class="fn-foot"><span class="fn-x">{naive / right:.2f}&times; overstated</span>
              {int(fr.get("CUSTOMERS") or 0):,} customers counted {int(fr.get("JOINED_ROWS") or 0):,} times, once per ticket.
              <b>Semantic Views refuses this until the grain is explicit.</b></div></div>''')

    # ---- the adoption path
    html('''<div class="ov-band"><div class="ov-k">The adoption path</div><div class="ov-h">Federate first. Accelerate what earns it.</div></div>
      <div class="path5">
        <div class="p5 done"><div class="p5-n">1</div><div class="p5-t">Attach</div><div class="p5-d">federate the sources</div><div class="p5-s">in this demo</div></div>
        <div class="p5 sv"><div class="p5-n">2</div><div class="p5-t">Model</div><div class="p5-d">entities, grain, metrics</div><div class="p5-s">Semantic Views</div></div>
        <div class="p5 sv"><div class="p5-n">3</div><div class="p5-t">Fuse</div><div class="p5-d">identity, authority</div><div class="p5-s">Semantic Views</div></div>
        <div class="p5 done"><div class="p5-n">4</div><div class="p5-t">Accelerate</div><div class="p5-d">import the hot paths</div><div class="p5-s">in this demo</div></div>
        <div class="p5"><div class="p5-n">5</div><div class="p5-t">Agent-enable</div><div class="p5-d">isolated workspaces</div><div class="p5-s">next step</div></div></div>''')

    # ---- shared bits for the visual sections
    def ico(paths, size=22):
        return (f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
                f'stroke-linecap="round" stroke-linejoin="round">{paths}</svg>')

    I = {"flask": '<path d="M9 3h6M10 3v6L4.5 19a1.5 1.5 0 0 0 1.3 2.2h12.4a1.5 1.5 0 0 0 1.3-2.2L14 9V3"/><path d="M7 15h10"/>',
         "tag": '<path d="M20 12l-8 8-9-9V3h8z"/><circle cx="7.5" cy="7.5" r="1.5"/>',
         "bucket": '<ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5l1.6 14c.2 1.7 3 3 6.4 3s6.2-1.3 6.4-3L20 5"/>',
         "cpu": '<rect x="6" y="6" width="12" height="12" rx="2"/><path d="M9 2v4M15 2v4M9 18v4M15 18v4M2 9h4M2 15h4M18 9h4M18 15h4"/>',
         "table": '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M3 10h18M9 10v10"/>',
         "copy": '<rect x="8" y="8" width="13" height="13" rx="2"/><path d="M16 8V5a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h3"/><path d="M4 4l16 16"/>',
         "vector": '<circle cx="6" cy="6" r="2"/><circle cx="18" cy="8" r="2"/><circle cx="9" cy="18" r="2"/><path d="M8 7l8 1M7.5 8l1 8M10.5 17l6-7.5"/>',
         "bolt": '<path d="M13 2L4 14h7l-1 8 9-12h-7z"/>',
         "link": '<path d="M10 14a5 5 0 0 0 7 0l3-3a5 5 0 0 0-7-7l-1 1"/><path d="M14 10a5 5 0 0 0-7 0l-3 3a5 5 0 0 0 7 7l1-1"/>',
         "shield": '<path d="M12 2l8 3v6c0 5-3.5 9-8 11-4.5-2-8-6-8-11V5z"/><path d="M8.5 12l2.5 2.5 4.5-5"/>',
         "eye": '<path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>'}

    def head(kick, title, line):
        html(f'<div class="ov-band"><div class="ov-k">{kick}</div><div class="ov-h">{title}</div>'
             f'<div class="ov-s">{line}</div></div>')

    # ---- MLflow: a pipeline, not a paragraph
    head("MLflow", "Keep your MLOps. Run the model where the data is.",
         "Train in MLflow as today; Exasol runs the registered model on all the data.")
    meta = db.run("cloud", Q_ML_META, key="ml_meta")
    m = meta["rows"][0] if meta["rows"] else {}
    chip = (f'churn v{m.get("VERSION")} &middot; {100 * float(m.get("ACCURACY") or 0):.0f}% on '
            f'{int(m.get("N_TEST") or 0):,} unseen tickets') if m else "model registry"
    steps = [("flask", "MLflow", "train &amp; track", ""), ("tag", "Registry", "model version", ""),
             ("bucket", "BucketFS", "artifact store", "exasol/mlflow-plugin"), ("cpu", "Python UDF", "scores in-database", "exa"),
             ("table", "Score tables", "SQL &amp; dashboards", "")]
    flow = ""
    for i, (ic, t, d, tag) in enumerate(steps):
        if i:
            flow += '<div class="pp-ar">&rarr;</div>'
        cls = " exa" if tag == "exa" else ""
        tg = f'<div class="pp-tg">{tag}</div>' if tag and tag != "exa" else ""
        flow += f'<div class="pp{cls}"><div class="pp-ic">{ico(I[ic], 26)}</div><div class="pp-t">{t}</div><div class="pp-d">{d}</div>{tg}</div>'
    html(f'<div class="pipe">{flow}</div><div class="pp-loop">&#8634; monitor drift and retrain, all from SQL'
         f'<span class="pp-chip">live in this demo: {chip}</span></div>')

    # ---- tokens: a bar chart
    raw, ans_tok, hero = token_budget()
    raw_tok = int((raw.get("TICKET_TOKENS") or 0) + (raw.get("CUSTOMER_TOKENS") or 0))
    ctx = 200_000
    ctx_pct = min(100, 100 * ctx / max(raw_tok, 1))
    ans_pct = max(0.25, 100 * ans_tok / max(raw_tok, 1))
    head("Fewer tokens", f"<span class='big-x'>{raw_tok / ans_tok:,.0f}&times;</span> fewer tokens per question",
         "Measured on this demo's tables: the raw data an LLM would need, against Exasol's answer.")
    html(f'''<div class="tbars">
      <div class="tb-row"><div class="tb-l">Raw data in the prompt<span>{int(raw.get("TICKETS") or 0):,} tickets + {int(raw.get("CUSTOMERS") or 0):,} customers</span></div>
        <div class="tb-tr"><div class="tb-f bad" style="width:100%"></div>
          <div class="tb-ctx" style="left:{ctx_pct:.1f}%"><span>200 k context window</span></div></div>
        <div class="tb-v bad">≈ {raw_tok / 1e6:,.2f} M</div></div>
      <div class="tb-row"><div class="tb-l">Exasol's answer<span>{len(hero["rows"])} rows, searched, scored, joined</span></div>
        <div class="tb-tr"><div class="tb-f good" style="width:{ans_pct:.2f}%"></div><div class="tb-pin" style="left:{ans_pct:.2f}%">&larr; this sliver</div></div>
        <div class="tb-v good">≈ {ans_tok:,}</div></div></div>''')

    # ---- Langfuse: a trace timeline
    head("Langfuse", "Every step, every token, every query",
         "How Langfuse would trace this question if an AI agent asked it through Exasol.")
    sql_s = float(hero.get("secs") or 0)
    spans = [("LLM", "llm", "Write the SQL", 0.0, 1.5, 1380), ("SQL", "sql", "exasol.query", 1.5, sql_s, ans_tok),
             ("LLM", "llm", "Write the answer", 1.5 + sql_s, 2.0, ans_tok + 520)]
    total_t = 1.5 + sql_s + 2.0
    total_tok = sum(s_[5] for s_ in spans)
    rows = ""
    for badge, cls, name, start, dur, tok in spans:
        rows += (f'<div class="lf-row"><div class="lf-n"><span class="lf-b {cls}">{badge}</span>{name}</div>'
                 f'<div class="lf-tr"><div class="lf-bar {cls}" style="left:{100 * start / total_t:.1f}%;width:{100 * dur / total_t:.1f}%">'
                 f'<span>{dur:.1f} s &middot; {tok:,} tok</span></div></div></div>')
    html(f'''<div class="lf"><div class="lf-hd"><span class="lf-dot"></span>trace &middot; Which unhappy customers put the most revenue at risk?
           <span class="lf-tot">{total_t:.1f} s &middot; ≈ {total_tok:,} tokens</span></div>{rows}
         <div class="lf-ax"><span>0 s</span><span>{total_t / 2:.1f} s</span><span>{total_t:.1f} s</span></div></div>''')
    html('<div class="footnote">Illustrative: the SQL step is measured live on this demo; LLM steps are estimates.</div>')

    html('<div class="footnote">Data: customers, orders and shipments are the public TPC-H benchmark; support tickets are synthetic.</div>')
