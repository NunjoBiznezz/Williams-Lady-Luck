"""Serialise shapely geometry to SVG paths using true circular arcs where the boundary lies on known circles."""
import numpy as np, sys
import curvefit as CF
CURVES=0   # set to a tolerance (px) to fit non-circle parts with Beziers
sys.path.insert(0,'lanes')
from build import ring_segs
from shapely import affinity
def _ring(coords,circles,tol=0.35,dx=0,dy=0,eps=0.3):
    P=np.asarray(coords)[:-1]; n=len(P)
    C=np.array(circles,float)
    on=np.abs(np.hypot(P[:,None,0]-C[None,:,0],P[:,None,1]-C[None,:,1])-C[None,:,2])<tol   # n x k membership
    seglab=np.full(n,-1)
    for i in range(n):
        j=(i+1)%n; both=np.where(on[i]&on[j])[0]
        if len(both):
            m=(P[i]+P[j])/2; both=both[np.abs(np.hypot(m[0]-C[both,0],m[1]-C[both,1])-C[both,2])<tol+0.3]   # reject chords
        if len(both):
            # pick the circle whose arc between the points is short (avoid chords of big circles)
            win=[(i+k)%n for k in range(-4,6)]
            seglab[i]=both[np.argmax(on[win][:,both].sum(0))]
    if (seglab==-1).all(): return None
    if (seglab==seglab[0]).all() and abs(_turn(np.vstack([P,P[:1]]),*circles[seglab[0]][:2]))>6:
        cx,cy,r=circles[seglab[0]]; sw=1 if _turn(np.vstack([P,P[:1]]),cx,cy)>0 else 0
        return (f'M{cx+r+dx:.2f},{cy+dy:.2f}A{r:.2f},{r:.2f} 0 1 {sw} {cx-r+dx:.2f},{cy+dy:.2f}'
                f'A{r:.2f},{r:.2f} 0 1 {sw} {cx+r+dx:.2f},{cy+dy:.2f}Z')
    k=next(i for i in range(n) if seglab[i]!=seglab[i-1]); P=np.roll(P,-k,0); seglab=np.roll(seglab,-k)
    out=f'M{P[0,0]+dx:.2f},{P[0,1]+dy:.2f}'; s=0
    from shapely.geometry import LineString
    for i in range(1,n+1):
        if i<n and seglab[i]==seglab[s]: continue
        pts=np.vstack([P[s:i],P[i%n][None]])          # vertices s..i (segments s..i-1)
        L=seglab[s]
        if L>=0:
            cx,cy,r=circles[L]; t=_turn(pts,cx,cy); pieces=max(1,int(np.ceil(abs(t)/(np.pi*0.9))))
            idx=np.linspace(0,len(pts)-1,pieces+1).round().astype(int)
            for u,v in zip(idx[:-1],idx[1:]):
                if v==u: continue
                q=pts[v]; tt=_turn(pts[u:v+1],cx,cy)
                out+=f'A{r:.2f},{r:.2f} 0 0 {1 if tt>0 else 0} {q[0]+dx:.2f},{q[1]+dy:.2f}'
        else:
            if CURVES and len(pts)>4:
                for c in CF.fit_open(pts,tol=CURVES):
                    out+=f'C{c[1][0]+dx:.2f},{c[1][1]+dy:.2f} {c[2][0]+dx:.2f},{c[2][1]+dy:.2f} {c[3][0]+dx:.2f},{c[3][1]+dy:.2f}'
            else:
                ls=LineString(pts).simplify(eps) if len(pts)>2 else LineString(pts)
                for q in np.asarray(ls.coords)[1:]: out+=f'L{q[0]+dx:.2f},{q[1]+dy:.2f}'
        s=i
    return out+'Z'
def _turn(seg,cx,cy):
    a=np.unwrap(np.arctan2(seg[:,1]-cy,seg[:,0]-cx)); return a[-1]-a[0]
def pathd(g,circles,dx=0,dy=0,minarea=2,eps=0.3):
    gs=[g] if g.geom_type=='Polygon' else [q for q in getattr(g,'geoms',[]) if q.geom_type=='Polygon']
    out=[]
    for q in gs:
        if q.area<minarea: continue
        for r in [q.exterior,*q.interiors]:
            from shapely.geometry import Polygon as _P
            if _P(r.coords).area<minarea: continue
            d=_ring(r.coords,circles,dx=dx,dy=dy,eps=eps)
            if d is None:
                d=CF.to_d(CF.fit_closed(np.asarray(r.coords)[:-1],tol=CURVES),dx,dy) if CURVES else ring_segs(affinity.translate(r,dx,dy).coords,eps=max(eps,0.25))[0]
            out.append(d)
    return ' '.join(out)
def count(d):
    import re; return len(re.findall(r'[ACL]',d))
