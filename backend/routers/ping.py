import ipaddress,re,subprocess,sys
from concurrent.futures import ThreadPoolExecutor
from fastapi import APIRouter, Request, Form
from ..templating import templates

router = APIRouter(prefix="/ping", tags=["ping"])
MAX_HOSTS=100; MAX_WORKERS=50; PING_TIMEOUT=1000

def expand_targets(text):
    ips=set()
    for part in re.split(r"[,\s\n]+",text.strip()):
        part=part.strip()
        if not part: continue
        try:
            if "/" in part:
                net=ipaddress.ip_network(part,strict=False)
                for ip in net.hosts():
                    ips.add(str(ip))
                    if len(ips)>=MAX_HOSTS: break
            elif "-" in part:
                a,b=part.split("-",1)
                s,e=int(ipaddress.IPv4Address(a.strip())),int(ipaddress.IPv4Address(b.strip()))
                for i in range(s,min(e+1,s+MAX_HOSTS)): ips.add(str(ipaddress.IPv4Address(i)))
            else:
                ipaddress.IPv4Address(part); ips.add(part)
        except: pass
    return sorted(ips,key=lambda x:ipaddress.IPv4Address(x))

def ping_one(ip):
    is_win=sys.platform=="win32"
    cmd=["ping","-n" if is_win else "-c","4","-w" if is_win else "-W",str(PING_TIMEOUT),ip]
    try:
        out=subprocess.run(cmd,capture_output=True,text=True,timeout=6)
        output=out.stdout+out.stderr
    except: return {"ip":ip,"reachable":False}
    if is_win:
        times=[int(m) for m in re.findall(r"time[=<]\s*(\d+)ms",output)]
    else:
        times=[float(m) for m in re.findall(r"time[=<]\s*(\d+\.?\d*)\s*ms",output)]
    if times:
        return {"ip":ip,"reachable":True,"avg_ms":f"{sum(times)/len(times):.1f}","min_ms":f"{min(times):.1f}","max_ms":f"{max(times):.1f}","sent":4,"recv":len(times)}
    return {"ip":ip,"reachable":False}

def do_trace(host):
    """Route tracing: tracert on Windows, mtr on Linux."""
    is_win = sys.platform == "win32"
    if is_win:
        cmd = ["tracert", "-d", "-w", str(PING_TIMEOUT), "-h", "20", host]
        try:
            out = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            return _parse_tracert(out.stdout + out.stderr)
        except:
            return None, "tracert failed"
    else:
        cmd = ["mtr", "--report", "--report-cycles=5", "-n", host]
        try:
            out = subprocess.run(cmd, capture_output=True, text=True, timeout=35)
            return _parse_mtr(out.stdout + out.stderr)
        except Exception as e:
            return None, f"mtr failed: {e}"

def _parse_tracert(output):
    hops = []
    for line in output.splitlines():
        m = re.search(r"^\s*(\d+)\s+", line)
        if m:
            ip_m = re.findall(r"(\d+\.\d+\.\d+\.\d+)", line)
            times = re.findall(r"([<\d]+\.?\d*)\s*ms", line)
            hops.append({"hop":m.group(1),"ip":ip_m[-1] if ip_m else "*","times":", ".join(t+"ms" for t in times[:3]) if times else "*"})
    return hops, output

def _parse_mtr(output):
    """Parse MTR report into hops format."""
    hops = []
    for line in output.splitlines():
        line = line.strip()
        if not line or line.startswith("Start") or line.startswith("HOST"):
            continue
        parts = line.split()
        if len(parts) >= 3 and parts[0].isdigit():
            hop_num = parts[0]
            ip = parts[1] if parts[1] != "???" else "*"
            times_str = ""
            if len(parts) >= 7:
                times_str = f"last={parts[4]}ms avg={parts[5]}ms best={parts[6]}ms loss={parts[2]}%"
            hops.append({"hop": hop_num, "ip": ip, "times": times_str or " ".join(parts[2:])})
    return hops, output

@router.get("")
def ping_page(request: Request):
    return templates.TemplateResponse(request, "ping.html", {})

@router.post("")
def ping_post(request: Request, targets: str=Form(default=""), trace_target: str=Form(default=""),
              cont_target: str=Form(default=""), cont_count: str=Form(default="4"),
              mtr_target: str=Form(default="")):
    # Raw MTR output
    if mtr_target.strip():
        cmd=["mtr","--report","--report-cycles=5","-n",mtr_target.strip()]
        try:
            out=subprocess.run(cmd,capture_output=True,text=True,timeout=35)
            return templates.TemplateResponse(request, "ping.html", {"mtr_host":mtr_target,"mtr_output":out.stdout+out.stderr})
        except Exception as e:
            return templates.TemplateResponse(request, "ping.html", {"mtr_host":mtr_target,"mtr_output":f"MTR error: {e}"})
    # Continuous ping
    if cont_target.strip():
        count=min(int(cont_count),100) if cont_count.isdigit() else 4
        is_win=sys.platform=="win32"
        cmd=["ping","-n" if is_win else "-c",str(count),"-w" if is_win else "-W",str(PING_TIMEOUT),cont_target.strip()]
        out=subprocess.run(cmd,capture_output=True,text=True,timeout=count*3+5)
        results=[]
        for line in (out.stdout+out.stderr).splitlines():
            m=re.search(r"time[=<]\s*(\d+\.?\d*)\s*ms",line)
            if m: results.append({"seq":len(results)+1,"reachable":True,"latency_ms":float(m.group(1))})
            elif "timed out" in line.lower() or "Request timed out" in line:
                results.append({"seq":len(results)+1,"reachable":False,"latency_ms":None})
        reachable=[r for r in results if r["reachable"]]
        latencies=[r["latency_ms"] for r in reachable]
        return templates.TemplateResponse(request, "ping.html", {
            "cont_host":cont_target,"cont_count":count,"cont_results":results,
            "cont_sent":len(results),"cont_recv":len(reachable),
            "cont_loss":f"{(1-len(reachable)/max(len(results),1))*100:.0f}%",
            "cont_min":f"{min(latencies):.1f}" if latencies else "-",
            "cont_max":f"{max(latencies):.1f}" if latencies else "-",
            "cont_avg":f"{sum(latencies)/len(latencies):.1f}" if latencies else "-"})
    # Route tracing (tracert on Windows, MTR on Linux)
    if trace_target.strip():
        hops,output=do_trace(trace_target.strip())
        if hops is None:
            return templates.TemplateResponse(request, "ping.html", {"error":output})
        return templates.TemplateResponse(request, "ping.html", {"trace_host":trace_target,"trace_hops":hops,"trace_raw":output})
    # Batch ping
    if not targets.strip():
        return templates.TemplateResponse(request, "ping.html", {"error":"enter IPs"})
    ips=expand_targets(targets)[:MAX_HOSTS]
    if not ips:
        return templates.TemplateResponse(request, "ping.html", {"error":"no valid IPs"})
    with ThreadPoolExecutor(max_workers=min(MAX_WORKERS,len(ips))) as pool:
        results=list(pool.map(ping_one,ips))
    reachable=[r for r in results if r["reachable"]]
    return templates.TemplateResponse(request, "ping.html", {"results":results,"total":len(results),"reachable":len(reachable),"unreachable":len(results)-len(reachable),"targets":targets})
