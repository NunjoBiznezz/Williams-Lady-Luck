"""Rebuild painted line art (label image: 0 outside, BLACK lines, other colour labels) as clean vector shapes:
outer outline and inner lines get one constant width each, every line is a few smooth Bezier curves,
sharp corners are kept sharp, colour regions are exactly the spaces between the lines."""
import numpy as np, cv2, networkx as nx
from skimage.morphology import skeletonize
from shapely.geometry import Polygon, LineString, Point
from shapely.ops import unary_union
import curvefit as CF

def _bez_pts(segs,n=24):
    return np.vstack([CF._bez(*c,np.linspace(0,1,n)[:-1]) for c in segs]+[segs[-1][3][None]])

def _single_fits(Q,tol):
    """fit an open polyline with as few cubics as possible (1 if it is a sweep)"""
    if len(Q)<4: return [(Q[0],Q[0]+(Q[-1]-Q[0])/3,Q[-1]-(Q[-1]-Q[0])/3,Q[-1])]
    return CF._fit(Q,CF._tan(Q,0,1,min(8,len(Q)-1)),CF._tan(Q,len(Q)-1,-1,min(8,len(Q)-1)),tol)

def _split_corners(Q,k=10,thr=30):
    n=len(Q); cs=[]
    if n>2*k+2:
        a=Q[k:-k]-Q[:-2*k]; b=Q[2*k:]-Q[k:-k]
        ang=np.degrees(np.abs(np.arctan2(a[:,0]*b[:,1]-a[:,1]*b[:,0],(a*b).sum(1))))
        for i in range(len(ang)):
            if ang[i]>thr and ang[i]>=ang[max(0,i-k):i+k+1].max() and all(abs(i+k-c)>2*k for c in cs): cs.append(i+k)
    return [0]+sorted(cs)+[n-1]

def _resample_open(P,step=1.0):
    d=np.r_[0,np.cumsum(np.hypot(*np.diff(P,axis=0).T))]
    if d[-1]<1e-6: return P[:1]
    t=np.r_[np.arange(0,d[-1],step),d[-1]]; return np.c_[np.interp(t,d,P[:,0]),np.interp(t,d,P[:,1])]

def _sharpen(pieces,P,cuts):
    """move each interior corner to the meeting point of the straight-ish lead-in/out (sharp tips)"""
    for j in range(1,len(pieces)):
        c=cuts[j]; n=len(P)
        if c<14 or c>n-15: continue
        A1,A2=P[max(0,c-36)],P[c-12]; B1,B2=P[c+12],P[min(n-1,c+36)]
        d1=A2-A1; d2=B2-B1; M=np.c_[d1,-d2]
        if abs(np.linalg.det(M))<1e-6: continue
        s,_=np.linalg.solve(M,B1-A2); X=A2+s*d1
        if np.linalg.norm(X-P[c])<25:
            pieces[j-1][-1]=X; pieces[j][0]=X
    return pieces

def fit_open_joints(P,joints,tol,cjoints=()):
    P=np.asarray(P,float)
    allj=sorted(set(list(joints)+list(cjoints))); isC={j:(j in cjoints) for j in allj}
    marks=[0]+allj+[len(P)-1]; R=[];J=[]
    for a,b in zip(marks[:-1],marks[1:]):
        seg=_resample_open(P[a:b+1]); R.append(seg if not R else seg[1:])
        J.append(sum(len(r) for r in R)-1)
    Q=np.vstack(R); J=J[:-1]
    Cj=[J[k] for k,j in enumerate(allj) if isC[j]]; J=[J[k] for k,j in enumerate(allj) if not isC[j]]
    n=len(Q)
    corners=[c for c in _split_corners(Q,k=14,thr=42)[1:-1] if all(abs(c-j)>12 for j in J+Cj)]
    hard=sorted(set(Cj+corners))
    # sharpen hard corners: put the vertex where the lead-in and lead-out lines meet
    for c in hard:
        if c<14 or c>n-15: continue
        A1,A2=Q[max(0,c-40)],Q[c-14]; B1,B2=Q[c+14],Q[min(n-1,c+40)]
        d1=A2-A1; d2=B2-B1; M=np.c_[d1,-d2]
        if abs(np.linalg.det(M))<1e-6: continue
        s_,_=np.linalg.solve(M,B1-A2); X=A2+s_*d1
        if np.linalg.norm(X-Q[c])<30:
            Q[c-13:c]=np.linspace(A2,X,14)[1:]; Q[c]=X; Q[c+1:c+14]=np.linspace(X,B1,14)[:-1]
    def fit_piece(a,b,t1=None,t2=None):
        S_=Q[a:b+1]
        if len(S_)<4: return [ (S_[0],S_[0]+(S_[-1]-S_[0])/3,S_[-1]-(S_[-1]-S_[0])/3,S_[-1]) ]
        t1=CF._tan(S_,0,1,min(10,len(S_)-1)) if t1 is None else t1
        t2=CF._tan(S_,len(S_)-1,-1,min(10,len(S_)-1)) if t2 is None else t2
        return CF._fit(S_,t1,t2,tol)
    def smooth_tan(j):
        a=Q[max(0,j-25)]; b=Q[min(n-1,j+25)]; t=b-a; return t/(np.linalg.norm(t)+1e-9)
    cuts=[0]+hard+[n-1]
    pieces=[]
    for a,b in zip(cuts[:-1],cuts[1:]):
        inner=[j for j in J if a+8<j<b-8]
        segs=fit_piece(a,b)
        pts=_bez_pts(segs,60)
        bad=[j for j in inner if np.min(np.hypot(*(pts-Q[j]).T))>2.5]
        if bad:   # split at the junctions it misses, keeping the curve smooth (shared tangent) there
            sub=[a]+bad+[b]; segs=[]
            for u,v in zip(sub[:-1],sub[1:]):
                segs+=fit_piece(u,v,None if u==a else smooth_tan(u),None if v==b else -smooth_tan(v))
        pieces.append(_bez_pts(segs))
    return np.vstack([pieces[0]]+[p[1:] for p in pieces[1:]]), len(pieces)

def fit_curve(P,tol=3.0,closed=False,thr=32,sharpen=True):
    """return dense polyline of a smooth fitted curve with sharp corners preserved"""
    P=np.asarray(P,float)
    if closed:
        P=CF._resample(P); cs,_=CF._corners(P,k=12,thr=30)
        if len(cs)<1: cs=[0]
        P=np.roll(P,-cs[0],0); cs=[c-cs[0] for c in cs]; P=np.vstack([P,P[:1]])
        cuts=cs+[len(P)-1]
    else:
        P=_resample_open(P); cuts=_split_corners(P,k=14,thr=thr)
    pieces=[]
    for a,b in zip(cuts[:-1],cuts[1:]):
        if b-a<2: continue
        Q=P[a:b+1].copy()
        if len(Q)>9:   # moving-average smoothing, ends fixed
            k=7; ker=np.ones(k)/k
            for d in (0,1):
                sm=np.convolve(np.r_[np.full(k,Q[0,d]),Q[:,d],np.full(k,Q[-1,d])],ker,'same')[k:-k]
                w=np.clip(np.minimum(np.arange(len(Q)),np.arange(len(Q))[::-1])/k,0,1); Q[:,d]=w*sm+(1-w)*Q[:,d]
        segs=_single_fits(Q,tol); pieces.append(_bez_pts(segs))
    if sharpen: pieces=_sharpen(pieces,P,cuts)
    out=np.vstack([pieces[0]]+[p[1:] for p in pieces[1:]])
    return out, sum(1 for _ in pieces)

def skeleton_branches(mask,min_len=12,edge=None,WO=13.0,up=2):
    m=cv2.resize(mask.astype(np.float32),(mask.shape[1]*up,mask.shape[0]*up),interpolation=cv2.INTER_LINEAR)
    m=cv2.GaussianBlur(m,(0,0),up*1.2)>0.5
    sk=skeletonize(m)
    ys,xs=np.nonzero(sk); G=nx.Graph(); S=set(zip(ys,xs))
    for y,x in S:
        G.add_node((y,x))
        for dy in (-1,0,1):
            for dx in (-1,0,1):
                if (dy or dx) and (y+dy,x+dx) in S: G.add_edge((y,x),(y+dy,x+dx))
    special=[v for v in G if G.degree(v)!=2]
    # cluster junction pixels
    J=nx.Graph(); J.add_nodes_from(special)
    for v in special:
        for w in G[v]:
            if w in J: J.add_edge(v,w)
    jpos={}
    for comp in nx.connected_components(J):
        c=np.mean([(x,y) for y,x in comp],0)/up
        for v in comp: jpos[v]=c
    branches=[]; seen=set()
    for s in special:
        for nb in G[s]:
            if nb in jpos: continue
            e=frozenset((s,nb))
            if e in seen: continue
            path=[s,nb]; seen.add(e); prev,cur=s,nb
            while cur not in jpos:
                nxt=[w for w in G[cur] if w!=prev]
                if not nxt: break
                prev,cur=cur,nxt[0]; seen.add(frozenset((prev,cur))); path.append(cur)
            pts=np.array([(x,y) for y,x in path],float)/up
            ends=[jpos.get(path[0]),jpos.get(path[-1])]
            deg=[len([v for v in G if jpos.get(v) is not None and np.allclose(jpos[v],e)]) if e is not None else 0 for e in ends]
            branches.append(dict(pts=pts,ends=ends,free=[G.degree(path[0])==1, G.degree(path[-1])==1]))
    # pure loops (no junctions)
    for comp in nx.connected_components(G):
        if all(G.degree(v)==2 for v in comp):
            cyc=nx.cycle_basis(G.subgraph(comp))
            if cyc: branches.append(dict(pts=np.array([(x,y) for y,x in cyc[0]],float)/up,loop=True))
    out=[]
    for b in branches:
        p=b['pts']
        if b.get('loop'): out.append(b); continue
        if not b['free'][0]: p[0]=b['ends'][0]
        if not b['free'][1]: p[-1]=b['ends'][1]
        L=np.hypot(*np.diff(p,axis=0).T).sum()
        if L<min_len and (b['free'][0] or b['free'][1]): continue      # spur
        if L<40 and b['free'][0] and b['free'][1]: continue             # isolated fleck
        if edge is not None and L<45 and any(b['free'][e] and edge.distance(Point(*p[0 if e==0 else -1]))>WO+12 for e in (0,1)): continue   # spur at apex/corner
        b['pts']=p; out.append(b)
    return merge_through(out)

def _dir(p,end,k=15):
    k=min(k,len(p)-1)
    v=(p[k]-p[0]) if end==0 else (p[-1-k]-p[-1]); return v/(np.linalg.norm(v)+1e-9)
def merge_through(bs,minang=145):
    """join branches that pass straight through a junction into one continuous line"""
    bs=[b for b in bs]
    changed=True
    while changed:
        changed=False
        ends={}
        for i,b in enumerate(bs):
            if b.get('loop'): continue
            for e in (0,1):
                if not b['free'][e]:
                    key=tuple(np.round(b['ends'][e],1)); ends.setdefault(key,[]).append((i,e))
        for key,lst in ends.items():
            best=None
            for a in range(len(lst)):
                for c in range(a+1,len(lst)):
                    (i,ei),(j,ej)=lst[a],lst[c]
                    if i==j: continue
                    ang=np.degrees(np.arccos(np.clip(np.dot(_dir(bs[i]['pts'],ei),_dir(bs[j]['pts'],ej)),-1,1)))
                    if ang>minang and (best is None or ang>best[0]): best=(ang,i,ei,j,ej)
            if best is None and len(lst)==2 and lst[0][0]!=lst[1][0]:
                (i,ei),(j,ej)=lst; best=(0,i,ei,j,ej); corner=True
            else: corner=False
            if best:
                _,i,ei,j,ej=best; P=bs[i]['pts']; Q=bs[j]['pts']
                A=P if ei==1 else P[::-1]; B=Q if ej==0 else Q[::-1]
                fe=[bs[i]['free'][1-ei],bs[j]['free'][1-ej]]; en=[bs[i]['ends'][1-ei],bs[j]['ends'][1-ej]]
                jA=list(bs[i].get('joints',[])) if ei==1 else [len(P)-1-x for x in bs[i].get('joints',[])]; jB=list(bs[j].get('joints',[])) if ej==0 else [len(Q)-1-x for x in bs[j].get('joints',[])]
                cA=list(bs[i].get('cjoints',[])) if ei==1 else [len(P)-1-x for x in bs[i].get('cjoints',[])]; cB=list(bs[j].get('cjoints',[])) if ej==0 else [len(Q)-1-x for x in bs[j].get('cjoints',[])]
                J_=jA+[len(A)-1+x for x in jB]; C_=cA+[len(A)-1+x for x in cB]
                (C_ if corner else J_).append(len(A)-1)
                nb=dict(pts=np.vstack([A,B[1:]]),free=fe,ends=en,joints=J_,cjoints=C_)
                bs=[b for k,b in enumerate(bs) if k not in (i,j)]+[nb]; changed=True; break
    return bs

def build(L,black=6,WO=13.0,WI=10.5,tol=12.0,tol_outer=6.0,T=4.0,inner_scale=1.0):
    fpm=(L>0).astype(np.uint8)
    cs,_=cv2.findContours(fpm,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_NONE)
    c=max(cs,key=cv2.contourArea)[:,0,:].astype(float)
    segs=CF.fit_closed(c,tol=tol_outer,sharpen=True); nseg=len(segs)
    sil=_bez_pts(segs)
    S=Polygon(sil).buffer(0)
    I=S.buffer(-WO,join_style=2,mitre_limit=10)
    # interior lines: black pixels not part of the outer band
    yy,xx=np.mgrid[0:L.shape[0],0:L.shape[1]]
    ring=np.zeros(L.shape,np.uint8); cv2.fillPoly(ring,[np.round(np.asarray(I.buffer(-WO*0.3).exterior.coords)).astype(np.int32)],1)
    B=(L==black)&(ring>0)
    B=cv2.morphologyEx(B.astype(np.uint8),cv2.MORPH_CLOSE,np.ones((3,3),np.uint8))>0
    strokes=[]; nb=0
    edge=S.exterior
    for b in skeleton_branches(B,edge=S.exterior,WO=WO):
        p=b['pts']
        dists=np.array([edge.distance(Point(*q)) for q in p[::3]])
        if not b.get('loop') and (b['free'][0] or b['free'][1]) and (dists.max()<WO*1.8 or (dists<WO*1.4).mean()>0.6): continue          # leftover of the outer line
        if not b.get('loop') and not b.get('joints'):
            Lb=np.hypot(*np.diff(p,axis=0).T).sum()
            for e in (0,1):
                if b['free'][e] and Lb<40 and edge.distance(Point(*p[0 if e==0 else -1]))>WO+12: Lb=-1
            if Lb<0: continue                                            # spur at a corner / apex
        if b.get('loop'):
            g=Polygon(_bez_pts(CF.fit_closed(p,tol=tol_outer,sharpen=True))).buffer(0); strokes.append(g.buffer(WI/2,join_style=2,mitre_limit=10).difference(g.buffer(-WI/2,join_style=2,mitre_limit=10))); continue
        # free ends near the outer outline: extend to it
        for end in (0,-1):
            if b['free'][end if end==0 else 1]:
                e=p[end]; d=edge.distance(Point(e))
                if d<2*WO+14:
                    t=p[end]-p[end+6 if end==0 else end-6]; t/=np.linalg.norm(t)+1e-9
                    ext=e+t*(d+WO/2)
                    p=np.vstack([ext,p]) if end==0 else np.vstack([p,ext])
        off=1 if (b['free'][0] and len(p)>len(b['pts'])) else 0
        if b.get('joints') or b.get('cjoints'):
            q,k=fit_open_joints(p,[j+off for j in b.get('joints',[])],tol,[j+off for j in b.get('cjoints',[])])
        else: q,k=fit_curve(p,tol)
        nb+=k
        strokes.append(LineString(q).buffer(WI/2,cap_style=2,join_style=2,mitre_limit=10))
    inner=unary_union(strokes).intersection(S) if strokes else Polygon()
    blackg=unary_union([S.difference(I),inner])
    regions=I.difference(inner)
    cols={}
    for r in getattr(regions,'geoms',[regions]):
        if r.area<20: continue
        m=np.zeros(L.shape,np.uint8); cv2.fillPoly(m,[np.round(np.asarray(r.exterior.coords)).astype(np.int32)],1)
        for h in r.interiors: cv2.fillPoly(m,[np.round(np.asarray(h.coords)).astype(np.int32)],0)
        v=L[(m>0)&(L!=black)&(L>0)]
        if not len(v): continue
        lab=int(np.bincount(v).argmax()); cols.setdefault(lab,[]).append(r)
    cols={k:unary_union(v) for k,v in cols.items()}
    return dict(S=S,I=I,black=blackg,cols=cols,nseg=nseg)

# ---------------------------------------------------------------------------------------------
# Region-boundary method: every black line is the boundary between two neighbouring colour regions.
def _order_path(pix):
    """order a set of (x,y) boundary points into polylines (split at branch points)"""
    S=set(map(tuple,pix)); G=nx.Graph()
    for p in S:
        G.add_node(p)
        for dx in (-1,0,1):
            for dy in (-1,0,1):
                q=(p[0]+dx,p[1]+dy)
                if (dx or dy) and q in S: G.add_edge(p,q)
    G=nx.minimum_spanning_tree(G)
    paths=[]
    for comp in nx.connected_components(G):
        H=G.subgraph(comp)
        if len(H)<2: continue
        # longest path in a tree via double BFS
        a=next(iter(H)); d=nx.single_source_shortest_path_length(H,a); b=max(d,key=d.get)
        d=nx.single_source_shortest_path_length(H,b); c=max(d,key=d.get)
        paths.append(np.array(nx.shortest_path(H,b,c),float))
    return paths

def build2(L,black=6,WO=13.0,WI=10.5,tol=12.0,tol_outer=6.0,smooth=3.0,minlen=15):
    H_,W_=L.shape
    fpm=(L>0).astype(np.uint8)
    cs,_=cv2.findContours(fpm,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_NONE)
    c=max(cs,key=cv2.contourArea)[:,0,:].astype(float)
    segs=CF.fit_closed(c,tol=tol_outer,sharpen=True)
    S=Polygon(_bez_pts(segs)).buffer(0); I=S.buffer(-WO,join_style=2,mitre_limit=10)
    # colour regions (connected components of non-black paint)
    col=((L>0)&(L!=black)).astype(np.uint8)
    n,rid=cv2.connectedComponents(col,connectivity=4)
    sizes=np.bincount(rid.ravel()); good=[i for i in range(1,n) if sizes[i]>150]
    keep=np.isin(rid,good)
    d,idx=cv2.distanceTransformWithLabels((~keep).astype(np.uint8),cv2.DIST_L2,5,labelType=cv2.DIST_LABEL_PIXEL)
    ys,xs=np.where(keep); lut=np.zeros(idx.max()+1,np.int32); lut[idx[ys,xs]]=rid[ys,xs]
    part=np.where(fpm>0,lut[idx],0)
    # smooth the partition (majority vote) to remove paint wobble
    ids=[0]+good; prob=np.stack([cv2.GaussianBlur((part==i).astype(np.float32),(0,0),smooth) for i in ids])
    part=np.array(ids)[np.argmax(prob,0)]
    regcol={i:int(np.bincount(L[rid==i]).argmax()) for i in good}
    # boundary points between two painted regions
    pairs={}
    for dy,dx in ((0,1),(1,0),(1,1),(1,-1)):
        a=part[max(0,-dy):H_-max(0,dy), max(0,-dx):W_-max(0,dx)]
        b=part[max(0,dy):, max(0,dx):W_+min(0,dx) if dx<0 else None][:a.shape[0],:a.shape[1]]
        m=(a!=b)&(a>0)&(b>0)
        yy,xx=np.nonzero(m)
        for y,x,u,v in zip(yy,xx,a[m],b[m]):
            key=(min(u,v),max(u,v)); pairs.setdefault(key,set()).add((x+max(0,-dx),y+max(0,-dy)))
    polylines=[]
    for key,pix in pairs.items():
        for p in _order_path(np.array(list(pix))):
            if len(p)>=minlen: polylines.append(p)
    # snap ends: cluster nearby endpoints (junctions) to a common point; extend ends near the outline
    ends=[(i,e,(p[0] if e==0 else p[-1])) for i,p in enumerate(polylines) for e in (0,1)]
    used=set()
    for a in range(len(ends)):
        if a in used: continue
        grp=[a]+[b for b in range(a+1,len(ends)) if b not in used and np.linalg.norm(ends[a][2]-ends[b][2])<9]
        if len(grp)>1:
            cpt=np.mean([ends[g][2] for g in grp],0)
            for g in grp:
                i,e,_=ends[g]; used.add(g)
                if e==0: polylines[i]=np.vstack([cpt,polylines[i]])
                else: polylines[i]=np.vstack([polylines[i],cpt])
    edge=S.exterior; strokes=[]; npieces=0
    for p in polylines:
        for e in (0,1):
            q=p[0] if e==0 else p[-1]; dd=edge.distance(Point(*q))
            if dd<WO*2.5:
                t=(p[0]-p[min(8,len(p)-1)]) if e==0 else (p[-1]-p[-1-min(8,len(p)-1)]); t/=np.linalg.norm(t)+1e-9
                ext=q+t*(dd+WO*0.5)
                p=np.vstack([ext,p]) if e==0 else np.vstack([p,ext])
        q,k=fit_curve(p,tol); npieces+=k
        strokes.append(LineString(q).buffer(WI/2,cap_style=1,join_style=2,mitre_limit=10))
    inner=unary_union(strokes).intersection(S) if strokes else Polygon()
    blackg=unary_union([S.difference(I),inner])
    regions=I.difference(inner); cols={}
    for r in getattr(regions,'geoms',[regions]):
        if r.area<20: continue
        m=np.zeros(L.shape,np.uint8); cv2.fillPoly(m,[np.round(np.asarray(r.exterior.coords)).astype(np.int32)],1)
        v=L[(m>0)&(L!=black)&(L>0)]
        if not len(v): continue
        lab=int(np.bincount(v).argmax()); cols.setdefault(lab,[]).append(r)
    return dict(S=S,I=I,black=blackg,cols={k:unary_union(v) for k,v in cols.items()},nseg=len(segs),nlines=len(polylines),npieces=npieces)

def build3(L,black=6,WO=13.0,WI=10.5,tol=2.5,tol_outer=6.0,smooth=4.0):
    """colour regions = smoothed partition of the painted area; black = what is left between them.
    Every interior line is exactly WI wide (each side pulled back WI/2), the outline WO wide."""
    H_,W_=L.shape
    fpm=(L>0).astype(np.uint8)
    cs,_=cv2.findContours(fpm,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_NONE)
    c=max(cs,key=cv2.contourArea)[:,0,:].astype(float)
    segs=CF.fit_closed(c,tol=tol_outer,sharpen=True)
    S=Polygon(_bez_pts(segs)).buffer(0); I=S.buffer(-WO,join_style=2,mitre_limit=10)
    rid=np.zeros(L.shape,np.int32); nxt=1
    for k in np.unique(L):
        if k in (0,black): continue
        n,cc=cv2.connectedComponents((L==k).astype(np.uint8),connectivity=4)
        rid[cc>0]=cc[cc>0]+nxt-1; nxt+=n-1
    sizes=np.bincount(rid.ravel()); good=[i for i in range(1,len(sizes)) if sizes[i]>150]
    keep=np.isin(rid,good)
    d,idx=cv2.distanceTransformWithLabels((~keep).astype(np.uint8),cv2.DIST_L2,5,labelType=cv2.DIST_LABEL_PIXEL)
    ys,xs=np.where(keep); lut=np.zeros(idx.max()+1,np.int32); lut[idx[ys,xs]]=rid[ys,xs]
    part=np.where(fpm>0,lut[idx],0)
    ids=[0]+good; prob=np.stack([cv2.GaussianBlur((part==i).astype(np.float32),(0,0),smooth) for i in ids])
    part=np.array(ids)[np.argmax(prob,0)]
    cols={}; nseg=len(segs)
    for i in good:
        m=(part==i).astype(np.uint8)
        if m.sum()<100: continue
        lab=int(np.bincount(L[(rid==i)]).argmax())
        cc,hier=cv2.findContours(m,cv2.RETR_CCOMP,cv2.CHAIN_APPROX_NONE)
        for ci,cnt in enumerate(cc):
            if hier[0][ci][3]!=-1 or cv2.contourArea(cnt)<100: continue
            sg=CF.fit_closed(cnt[:,0,:].astype(float),tol=tol,sharpen=True,collapse=False); nseg+=len(sg)
            R=Polygon(_bez_pts(sg)).buffer(0)
            j=hier[0][ci][2]
            while j!=-1:
                if cv2.contourArea(cc[j])>100:
                    sh=CF.fit_closed(cc[j][:,0,:].astype(float),tol=tol,sharpen=True,collapse=False); nseg+=len(sh)
                    R=R.difference(Polygon(_bez_pts(sh)).buffer(0))
                j=hier[0][j][0]
            R=R.buffer(-WI/2,join_style=2,mitre_limit=10).intersection(I)
            if not R.is_empty: cols.setdefault(lab,[]).append(R)
    cols={k:unary_union(v) for k,v in cols.items()}
    blackg=S.difference(unary_union(list(cols.values())))
    return dict(S=S,I=I,black=blackg,cols=cols,nseg=nseg)

def _crack_chains(part):
    """planar boundary graph of a label image: chains of pixel-corner points between junctions, each with its label pair"""
    P=np.pad(part,1,constant_values=0); H,W=P.shape
    G=nx.Graph()
    a=P[:-1,:]; b=P[1:,:]; ys,xs=np.nonzero(a!=b)        # horizontal cracks
    for y,x in zip(ys,xs): G.add_edge((x,y+1),(x+1,y+1),pair=(min(a[y,x],b[y,x]),max(a[y,x],b[y,x])))
    a=P[:,:-1]; b=P[:,1:]; ys,xs=np.nonzero(a!=b)        # vertical cracks
    for y,x in zip(ys,xs): G.add_edge((x+1,y),(x+1,y+1),pair=(min(a[y,x],b[y,x]),max(a[y,x],b[y,x])))
    def is_node(v):
        if G.degree(v)!=2: return True
        p=[G.edges[v,w]['pair'] for w in G[v]]; return p[0]!=p[1]
    nodes=set(v for v in G if is_node(v)); chains=[]; seen=set()
    for s in nodes:
        for w in G[s]:
            e=frozenset((s,w))
            if e in seen: continue
            path=[s,w]; seen.add(e); prev,cur=s,w
            while cur not in nodes:
                nx_=[u for u in G[cur] if u!=prev][0]; seen.add(frozenset((cur,nx_))); prev,cur=cur,nx_; path.append(cur)
            chains.append((G.edges[s,w]['pair'],np.array(path,float)-1))
    for comp in nx.connected_components(G):                # loops without junctions
        if not (set(comp)&nodes):
            cyc=nx.cycle_basis(G.subgraph(comp))[0]; v0,v1=cyc[0],cyc[1]
            chains.append((G.edges[v0,v1]['pair'],np.array(cyc+[cyc[0]],float)-1))
    return chains

def build4(L,black=6,WO=13.0,WI=10.5,tol=6.0,tol_outer=6.0,smooth=5.0,thr=55,mlim=2.0):
    from shapely.ops import polygonize, unary_union as UU
    from scipy import ndimage as ndi
    fill=ndi.binary_fill_holes(L>0); L=L.copy(); L[fill&(L==0)]=black      # unknown pixels inside the art count as line
    fpm=fill.astype(np.uint8)
    cs,_=cv2.findContours(fpm,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_NONE)
    c=max(cs,key=cv2.contourArea)[:,0,:].astype(float)
    segs=CF.fit_closed(c,tol=tol_outer,sharpen=True)
    S=Polygon(_bez_pts(segs)).buffer(0); I=S.buffer(-WO,join_style=2,mitre_limit=10)
    rid=np.zeros(L.shape,np.int32); nxt=1
    for k in np.unique(L):
        if k in (0,black): continue
        n,cc=cv2.connectedComponents((L==k).astype(np.uint8),connectivity=4)
        rid[cc>0]=cc[cc>0]+nxt-1; nxt+=n-1
    sizes=np.bincount(rid.ravel()); good=[i for i in range(1,len(sizes)) if sizes[i]>150]
    keep=np.isin(rid,good)
    d,idx=cv2.distanceTransformWithLabels((~keep).astype(np.uint8),cv2.DIST_L2,5,labelType=cv2.DIST_LABEL_PIXEL)
    ys,xs=np.where(keep); lut=np.zeros(idx.max()+1,np.int32); lut[idx[ys,xs]]=rid[ys,xs]
    part=np.where(fpm>0,lut[idx],0)
    ids=[0]+good; prob=np.stack([cv2.GaussianBlur((part==i).astype(np.float32),(0,0),smooth) for i in ids])
    part=np.array(ids)[np.argmax(prob,0)]
    # remove tiny islands created by the vote
    for i in good:
        n,cc,st,_=cv2.connectedComponentsWithStats((part==i).astype(np.uint8),connectivity=4)
        if n>2:
            big=1+np.argmax(st[1:,4])
            for j in range(1,n):
                if j!=big: part[cc==j]=0 if st[j,4]<50 else part[cc==j]
    regcol={i:int(np.bincount(L[rid==i]).argmax()) for i in good}
    lines=[]; npieces=0
    blk=cv2.dilate((L==black).astype(np.uint8),np.ones((5,5),np.uint8))
    for pair,pts in _crack_chains(part):
        if 0 not in pair:
            xi=np.clip(np.round(pts[:,0]).astype(int),0,L.shape[1]-1); yi=np.clip(np.round(pts[:,1]).astype(int),0,L.shape[0]-1)
            if blk[yi,xi].mean()<0.5: continue          # no painted line here: not a real boundary
        closed=np.allclose(pts[0],pts[-1]) and len(pts)>4
        if closed:
            q=_bez_pts(CF.fit_closed(pts[:-1],tol=tol,sharpen=True,collapse=False)); q=np.vstack([q,q[:1]])
        elif len(pts)>3:
            q,k=fit_curve(pts,tol,thr=thr,sharpen=False); npieces+=k; q[0]=pts[0]; q[-1]=pts[-1]
        else: q=pts
        lines.append(LineString(q))
    noded=UU(lines)
    polys=list(polygonize(noded))
    cols={}
    for r in polys:
        if r.area<30: continue
        m=np.zeros(L.shape,np.uint8); cv2.fillPoly(m,[np.round(np.asarray(r.exterior.coords)).astype(np.int32)],1)
        for h in r.interiors: cv2.fillPoly(m,[np.round(np.asarray(h.coords)).astype(np.int32)],0)
        v=part[(m>0)&(part>0)]
        if not len(v):
            rp=r.representative_point(); v=part[max(0,min(L.shape[0]-1,int(rp.y))),max(0,min(L.shape[1]-1,int(rp.x)))][None]
            if v[0]==0: continue
        rgn=int(np.bincount(v).argmax())
        R=r.buffer(-WI/2,join_style=1,quad_segs=8).intersection(I)
        if not R.is_empty: cols.setdefault(regcol[rgn],[]).append(R)
    cols={k:unary_union(v) for k,v in cols.items()}
    blackg=S.difference(unary_union(list(cols.values())))
    return dict(S=S,I=I,black=blackg,cols=cols,nseg=len(segs),npieces=npieces,nlines=len(lines),part=part,lines=lines,regcol=regcol)

def _odir(P,end,k=20):
    k=min(k,len(P)-1)
    v=(P[0]-P[k]) if end==0 else (P[-1]-P[-1-k]); n=np.linalg.norm(v); return v/n if n else v
def build5(L,black=6,WO=13.0,WI=10.5,tol=12.0,tol_outer=6.0,smooth=6.0,thr=55,minang=150,ext=8.0,sig=8.0):
    """planar map like build4, but lines run continuously through T-junctions
    (merged before fitting) and branch lines are extended to meet them"""
    from shapely.ops import polygonize, unary_union as UU
    from scipy import ndimage as ndi
    r4=build4(L,black,WO,WI,tol,tol_outer,smooth,thr)        # reuse the partition / outline
    part=r4['part']; S=r4['S']; I=r4['I']
    L=L.copy(); fill=ndi.binary_fill_holes(L>0); L[fill&(L==0)]=black
    blk=cv2.dilate((L==black).astype(np.uint8),np.ones((5,5),np.uint8))
    ch=[]
    for pair,pts in _crack_chains(part):
        if 0 not in pair:
            xi=np.clip(np.round(pts[:,0]).astype(int),0,L.shape[1]-1); yi=np.clip(np.round(pts[:,1]).astype(int),0,L.shape[0]-1)
            if blk[yi,xi].mean()<0.5: continue
        ch.append(np.asarray(pts,float))
    closed=[c for c in ch if np.allclose(c[0],c[-1]) and len(c)>4]
    opn=[c for c in ch if not (np.allclose(c[0],c[-1]) and len(c)>4)]
    # merge straight-through pairs at junctions
    changed=True
    while changed:
        changed=False; nodes={}
        for i,c in enumerate(opn):
            for e in (0,1): nodes.setdefault(tuple(np.round(c[-e],1)),[]).append((i,e))
        best=None
        for key,lst in nodes.items():
            for a in range(len(lst)):
                for b in range(a+1,len(lst)):
                    (i,ei),(j,ej)=lst[a],lst[b]
                    if i==j: continue
                    ang=np.degrees(np.arccos(np.clip(np.dot(_odir(opn[i],ei),_odir(opn[j],ej)),-1,1)))
                    if ang>minang and (best is None or ang>best[0]): best=(ang,i,ei,j,ej)
        if best:
            _,i,ei,j,ej=best; A=opn[i] if ei==1 else opn[i][::-1]; B=opn[j] if ej==0 else opn[j][::-1]
            opn=[c for k,c in enumerate(opn) if k not in (i,j)]+[np.vstack([A,B[1:]])]; changed=True
    lines=[]
    for c in closed:
        q=_bez_pts(CF.fit_closed(smooth_chain(c,sig,closed=True),tol=tol,sharpen=True,collapse=False)); lines.append(LineString(np.vstack([q,q[:1]])))
    deg={}
    for c in opn:
        for e in (0,1): k=tuple(np.round(c[-e],1)); deg[k]=deg.get(k,0)+1
    for c in opn:
        if len(c)>3:
            cs=smooth_chain(c,sig); q,_=fit_curve(cs,tol,thr=thr,sharpen=False); q=np.asarray(q,float); q[0]=c[0]; q[-1]=c[-1]
        else: q=c.copy()
        # extend ends that stop on another line so they cross it after fitting
        a=q[0]+_odir(q,0,3)*ext; b=q[-1]+_odir(q,1,3)*ext
        lines.append(LineString(np.vstack([a,q,b])))
    noded=UU(lines+[S.exterior])
    cols={}
    for r in polygonize(noded):
        if r.area<30: continue
        m=np.zeros(L.shape,np.uint8); cv2.fillPoly(m,[np.round(np.asarray(r.exterior.coords)).astype(np.int32)],1)
        for h in r.interiors: cv2.fillPoly(m,[np.round(np.asarray(h.coords)).astype(np.int32)],0)
        v=part[(m>0)&(part>0)]
        if len(v)<0.5*m.sum(): continue
        rgn=int(np.bincount(v).argmax()); col=r4["regcol"][rgn]
        R=r.buffer(-WI/2,join_style=1,quad_segs=8).intersection(I)
        if not R.is_empty: cols.setdefault(col,[]).append(R)
    cols={k:unary_union(v) for k,v in cols.items()}
    return dict(S=S,I=I,black=S.difference(unary_union(list(cols.values()))),cols=cols,part=part,lines=lines,nseg=r4['nseg'],npieces=0,nlines=len(lines))

def smooth_chain(P,sigma=8.0,closed=False,k=15,thr=50):
    """resample to 1px and Gaussian-smooth along the chain, keeping corners and end points fixed"""
    from scipy.ndimage import gaussian_filter1d as g1
    P=np.asarray(P,float)
    if closed:
        Q=CF._resample(P[:-1] if np.allclose(P[0],P[-1]) else P,1.0)
        c,_=CF._corners(Q,k=k,thr=thr)
        if not c: return np.c_[g1(Q[:,0],sigma,mode='wrap'),g1(Q[:,1],sigma,mode='wrap')]
        Q=np.roll(Q,-c[0],0); c=[i-c[0] for i in c]+[len(Q)]; Q=np.vstack([Q,Q[:1]])
    else:
        d=np.r_[0,np.cumsum(np.hypot(*np.diff(P,axis=0).T))]; t=np.arange(0,d[-1],1.0); t=np.r_[t,d[-1]]
        Q=np.c_[np.interp(t,d,P[:,0]),np.interp(t,d,P[:,1])]
        if len(Q)>2*k+2:
            n=len(Q); a=Q[k:-k]-Q[:-2*k]; b=Q[2*k:]-Q[k:-k]
            ang=np.degrees(np.abs(np.arctan2(a[:,0]*b[:,1]-a[:,1]*b[:,0],(a*b).sum(1))))
            c=[0]+[i+k for i in range(len(ang)) if ang[i]>thr and ang[i]>=ang[max(0,i-k):i+k+1].max()]+[n-1]
            c=sorted(set(c))
        else: c=[0,len(Q)-1]
    out=[]
    for a,b in zip(c[:-1],c[1:]):
        S=Q[a:b+1]
        if len(S)>4:
            sg=min(sigma,len(S)/4)
            sm=np.c_[g1(S[:,0],sg,mode='nearest'),g1(S[:,1],sg,mode='nearest')]
            w=np.linspace(0,1,len(S))[:,None]; sm=sm-((1-w)*(sm[0]-S[0])+w*(sm[-1]-S[-1]))
        else: sm=S
        out.append(sm if not out else sm[1:])
    R=np.vstack(out)
    return R[:-1] if closed else R
