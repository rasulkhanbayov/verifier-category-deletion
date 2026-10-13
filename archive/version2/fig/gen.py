import numpy as np
W=dict(blk='000000',org='E69F00',sky='56B4E9',grn='009E73',
       yel='F0E442',blu='0072B2',ver='D55E00',pur='CC79A7')
def g(p0,p,eps):
    q=p+(1-p)*eps
    return (1-p0)*(1-eps)*p/q if q>0 else 0.0
def A_N(p0,p,eps,N):
    q=p+(1-p)*eps
    return p0+(1-p0)*(1-eps)*(1-(1-q)**N)*(p/q) if q>0 else p0

out=[]
# ---------- iso-gain contours over (eps, p0) at p=0.55 ----------
P=0.55
out.append("%% ISO-GAIN CONTOURS  (x=eps in [0,1]->[0,4.2], y=p0 in [0,1]->[0,3.2])")
for lev in [0.05,0.10,0.20,0.30,0.40]:
    pts=[]
    for i in range(0,101):
        e=i/100.0
        q=P+(1-P)*e; f=(1-e)*P/q
        if f<=1e-9: continue
        p0=1-lev/f
        if 0.0<=p0<=1.0: pts.append(f"({e*4.2:.3f},{p0*3.2:.3f})")
    if len(pts)>1:
        out.append(f"\\draw[isog] plot coordinates {{{' '.join(pts)}}};  % gain={lev}")
        # label position at the right end
        e,p0=[float(x) for x in pts[-1].strip('()').split(',')]
        out.append(f"\\node[isolab] at ({e:.3f},{p0:.3f}) {{{lev:.2f}}};")

# ---------- degradation boundary in (eps, delta) at p0=0.75,p=0.55 ----------
p0d,pd=0.75,0.55
out.append("\n%% DEGRADATION BOUNDARY (x=eps->[0,4.2], y=delta in [0,0.5]->[0,3.2])")
pts=[]
for i in range(0,201):
    e=i/200.0
    lo,hi=0.0,1.0
    def val(d):
        qp=pd*(1-d)+(1-pd)*e
        if qp<=0: return -1.0
        r=pd*(1-d)/qp
        return p0d*d*(1-r)-(1-p0d)*(1-e)*r
    if val(1.0)<0: continue
    for _ in range(60):
        m=(lo+hi)/2
        if val(m)<0: lo=m
        else: hi=m
    d=(lo+hi)/2
    if d<=0.5: pts.append(f"({e*4.2:.3f},{d/0.5*3.2:.3f})")
out.append(f"\\draw[degb] plot coordinates {{{' '.join(pts)}}};")
print("degradation boundary pts:",len(pts),"delta* at eps=0.2:",
      [p for p in pts if abs(float(p.strip('()').split(',')[0])-0.84)<0.02][:1])

# ---------- finite-N convergence ----------
out.append("\n%% FINITE-N  (x=log2 N in [0,5]->[0,4.2], y=gain in [0,0.45]->[0,3.2])")
for eps,col,lab in [(0.10,'blu','0.1'),(0.40,'org','0.4'),(0.70,'grn','0.7'),(0.90,'ver','0.9')]:
    pts=[]
    for k in range(0,51):
        L=k/10.0; N=2**L
        v=A_N(0.55,P,eps,N)-0.55
        pts.append(f"({L/5*4.2:.3f},{v/0.45*3.2:.3f})")
    out.append(f"\\draw[c{col}] plot coordinates {{{' '.join(pts)}}};  % eps={lab}")
    v=A_N(0.55,P,eps,32)-0.55
    out.append(f"\\node[endlab,text={col}c] at (4.32,{v/0.45*3.2:.3f}) {{$\\varepsilon{{=}}{lab}$}};")

# ---------- gain vs eps, three p0 ----------
out.append("\n%% GAIN vs EPS (x=eps->[0,4.2], y=gain in [0,0.5]->[0,3.2])")
for p0,col,lab in [(0.55,'blu','0.55'),(0.70,'org','0.70'),(0.85,'grn','0.85')]:
    pts=[f"({(i/100)*4.2:.3f},{g(p0,P,i/100)/0.5*3.2:.3f})" for i in range(0,101)]
    out.append(f"\\draw[c{col}] plot coordinates {{{' '.join(pts)}}};  % p0={lab}")
open('tikz_data.tex','w').write('\n'.join(out))
print("wrote tikz_data.tex", len(out),"lines")
print("sanity: g(.55,.55,0)=",round(g(.55,P,0),3)," g(.55,.55,.9)=",round(g(.55,P,.9),4))
