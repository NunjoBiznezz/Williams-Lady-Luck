"""Fit a closed polyline with few cubic Beziers: sharp corners kept (and sharpened), smooth sweeps as single curves."""
import numpy as np
def _resample(P,step=1.0):
    P=np.vstack([P,P[:1]]); d=np.r_[0,np.cumsum(np.hypot(*np.diff(P,axis=0).T))]
    t=np.arange(0,d[-1],step); return np.c_[np.interp(t,d,P[:,0]),np.interp(t,d,P[:,1])]
def _corners(P,k=12,thr=38):
    n=len(P); a=P-np.roll(P,k,0); b=np.roll(P,-k,0)-P
    ang=np.degrees(np.abs(np.arctan2(a[:,0]*b[:,1]-a[:,1]*b[:,0],(a*b).sum(1))))
    c=[i for i in range(n) if ang[i]>thr and ang[i]>=ang[(i-np.arange(1,k+1))%n].max() and ang[i]>ang[(i+np.arange(1,k+1))%n].max()]
    # suppress corners closer than 20 samples (keep the sharper one)
    c=sorted(c,key=lambda i:-ang[i]); keep=[]
    for i in c:
        if all(min(abs(i-j),n-abs(i-j))>=20 for j in keep): keep.append(i)
    return sorted(keep),ang
def _bez(p0,p1,p2,p3,t):
    t=t[:,None]; return (1-t)**3*p0+3*(1-t)**2*t*p1+3*(1-t)*t*t*p2+t**3*p3
def _fit(Q,t1,t2,tol,depth=0):
    """Schneider-style fit of points Q with end tangents t1 (out of Q[0]) t2 (into Q[-1], pointing back)."""
    n=len(Q)
    if n<=3:
        L=np.linalg.norm(Q[-1]-Q[0])/3; return [(Q[0],Q[0]+t1*L,Q[-1]+t2*L,Q[-1])]
    u=np.r_[0,np.cumsum(np.hypot(*np.diff(Q,axis=0).T))]; u/=u[-1]
    for it in range(4):
        b0=(1-u)**3; b1=3*(1-u)**2*u; b2=3*(1-u)*u*u; b3=u**3
        A1=t1[None]*b1[:,None]; A2=t2[None]*b2[:,None]
        C=np.array([[np.sum(A1*A1),np.sum(A1*A2)],[np.sum(A1*A2),np.sum(A2*A2)]])
        R=Q-(b0+b1)[:,None]*Q[0]-(b2+b3)[:,None]*Q[-1]
        X=np.array([np.sum(A1*R),np.sum(A2*R)])
        try: a1,a2=np.linalg.solve(C,X)
        except np.linalg.LinAlgError: a1=a2=-1
        seg=np.linalg.norm(Q[-1]-Q[0])
        if a1<seg*1e-3 or a2<seg*1e-3: a1=a2=seg/3
        c=(Q[0],Q[0]+t1*a1,Q[-1]+t2*a2,Q[-1])
        B=_bez(*c,u); err=np.hypot(*(B-Q).T)
        # reparameterise (one Newton step)
        tt=u[:,None]; d1=3*((1-tt)**2*(c[1]-c[0])+2*(1-tt)*tt*(c[2]-c[1])+tt*tt*(c[3]-c[2]))
        d2=6*((1-tt)*(c[2]-2*c[1]+c[0])+tt*(c[3]-2*c[2]+c[1]))
        num=((B-Q)*d1).sum(1); den=(d1*d1).sum(1)+((B-Q)*d2).sum(1)
        u=np.clip(u-np.where(np.abs(den)>1e-9,num/den,0),0,1); u[0]=0; u[-1]=1; u=np.maximum.accumulate(u)
    if err.max()<=tol or depth>8: return [c]
    m=int(np.argmax(err)); m=min(max(m,2),n-3)
    tc=Q[m+1]-Q[m-1]; tc=tc/np.linalg.norm(tc)
    return _fit(Q[:m+1],t1,-tc,tol,depth+1)+_fit(Q[m:],tc,t2,tol,depth+1)
def _tan(Q,i,dirn,k=6):
    j=np.clip(i+dirn*k,0,len(Q)-1); v=Q[j]-Q[i]; return v/(np.linalg.norm(v)+1e-9)
def fit_closed(P,tol=1.5,sharpen=False,thr=38,collapse=True):
    P=_resample(np.asarray(P,float))
    cs,_=_corners(P,thr=thr)
    if sharpen and collapse and len(cs)>=2 and len(P)>400:
        # blunt / worn tips show up as two corners close together: replace the flat end by the point where the sides meet
        n=len(P); drop=np.zeros(n,bool); add={}
        for a,b in zip(cs,cs[1:]+[cs[0]+n]):
            if 4<b-a<=70:
                A1,A2=P[(a-40)%n],P[(a-12)%n]; B1,B2=P[(b+12)%n],P[(b+40)%n]
                d1=A2-A1; d2=B2-B1; M=np.c_[d1,-d2]
                if abs(np.linalg.det(M))<1e-6: continue
                s_,t_=np.linalg.solve(M,B1-A2); X=A2+s_*d1
                if np.linalg.norm(X-P[((a+b)//2)%n])<70 and np.linalg.norm(P[b%n]-P[a])<45:
                    idx=np.arange(a-11,b+12)%n; drop[idx]=True; add[(a-11)%n]=X
        if drop.any():
            Q=[]
            for i in range(n):
                if i in add: Q.append(add[i])
                if not drop[i]: Q.append(P[i])
            P=_resample(np.array(Q)); cs,_=_corners(P,thr=thr)
    if not cs:   # smooth closed curve: split at two opposite points
        cs=[0,len(P)//2]; smooth=True
    else: smooth=False
    cs=sorted(cs); n=len(P); curves=[]
    pieces=[]
    for a,b in zip(cs,cs[1:]+[cs[0]+n]):
        idx=np.arange(a,b+1)%n; pieces.append(P[idx])
    for Q in pieces:
        if smooth:
            t1=_tan(np.vstack([P[-6:],Q]),6,1); t2=_tan(np.vstack([Q,P[:6]]),len(Q)-1,-1)
        else:
            t1=_tan(Q,0,1); t2=_tan(Q,len(Q)-1,-1)
        curves.append(_fit(Q,t1,t2,tol))
    if sharpen and not smooth:
        # move each corner to where the straight-ish lead-in and lead-out lines meet (restores sharp tips)
        m=len(curves)
        for i in range(m):
            c=cs[i]; A1,A2=P[(c-36)%n],P[(c-14)%n]; B1,B2=P[(c+14)%n],P[(c+36)%n]
            d1=A2-A1; d2=B2-B1
            if np.linalg.norm(d1)<1e-6 or np.linalg.norm(d2)<1e-6: continue
            d1/=np.linalg.norm(d1); d2/=np.linalg.norm(d2); M=np.c_[d1,-d2]
            if abs(np.linalg.det(M))<0.05: continue
            s_,t_=np.linalg.solve(M,B1-A2); X=A2+s_*d1
            if np.linalg.norm(X-P[c])<40:
                cin=curves[i-1][-1]; cout=curves[i][0]
                shift=X-P[c]
                # keep the end tangents pointing along the lead lines so the tip stays a clean point
                L1=np.linalg.norm(cin[3]-cin[2]); L2=np.linalg.norm(cout[1]-cout[0])
                curves[i-1][-1]=(cin[0],cin[1],X-d1*L1,X); curves[i][0]=(X,X+d2*L2,cout[2],cout[3])
    segs=[list(c) for cl in curves for c in cl]
    if sharpen and collapse: segs=_kill_tiny(segs)
    return [tuple(c) for c in segs]
def _kill_tiny(segs,minchord=40):
    changed=True
    while changed and len(segs)>3:
        changed=False
        for i,c in enumerate(segs):
            if np.linalg.norm(np.asarray(c[3])-np.asarray(c[0]))<minchord:
                a=segs[i-1]; b=segs[(i+1)%len(segs)]
                d1=np.asarray(a[3])-np.asarray(a[2]); d2=np.asarray(b[1])-np.asarray(b[0])
                if np.linalg.norm(d1)<1e-6: d1=np.asarray(a[3])-np.asarray(a[0])
                if np.linalg.norm(d2)<1e-6: d2=np.asarray(b[3])-np.asarray(b[0])
                d1=d1/np.linalg.norm(d1); d2=d2/np.linalg.norm(d2); M=np.c_[d1,-d2]
                mid=(np.asarray(c[0])+np.asarray(c[3]))/2; X=mid
                if abs(np.linalg.det(M))>0.05:
                    s_,t_=np.linalg.solve(M,np.asarray(b[0])-np.asarray(a[3])); Y=np.asarray(a[3])+s_*d1
                    if np.linalg.norm(Y-mid)<30: X=Y
                L1=np.linalg.norm(np.asarray(a[3])-np.asarray(a[2])); L2=np.linalg.norm(np.asarray(b[1])-np.asarray(b[0]))
                a[3]=X; a[2]=X-d1*L1; b[0]=X; b[1]=X+d2*L2
                del segs[i]; changed=True; break
    return segs
def to_d(segs,dx=0,dy=0):
    p=segs[0][0]; s=f'M{p[0]+dx:.2f},{p[1]+dy:.2f}'
    for c in segs:
        p1,p2,p3=c[1],c[2],c[3]
        s+=f'C{p1[0]+dx:.2f},{p1[1]+dy:.2f} {p2[0]+dx:.2f},{p2[1]+dy:.2f} {p3[0]+dx:.2f},{p3[1]+dy:.2f}'
    return s+'Z'
def fit_open(P,tol=1.5,thr=38):
    P=np.asarray(P,float)
    d=np.r_[0,np.cumsum(np.hypot(*np.diff(P,axis=0).T))]
    if d[-1]<3: return [(P[0],P[0]+(P[-1]-P[0])/3,P[-1]-(P[-1]-P[0])/3,P[-1])]
    t=np.arange(0,d[-1],1.0); t=np.r_[t,d[-1]]
    Q=np.c_[np.interp(t,d,P[:,0]),np.interp(t,d,P[:,1])]
    n=len(Q); k=min(7,max(1,n//4))
    cs=[]
    if n>2*k+2:
        a=Q[k:-k]-Q[:-2*k]; b=Q[2*k:]-Q[k:-k]
        ang=np.degrees(np.abs(np.arctan2(a[:,0]*b[:,1]-a[:,1]*b[:,0],(a*b).sum(1))))
        for i in range(len(ang)):
            if ang[i]>thr and ang[i]>=ang[max(0,i-k):i+k+1].max(): cs.append(i+k)
    cuts=[0]+cs+[n-1]; out=[]
    for a_,b_ in zip(cuts[:-1],cuts[1:]):
        R=Q[a_:b_+1]
        if len(R)<2: continue
        out+=_fit(R,_tan(R,0,1),_tan(R,len(R)-1,-1),tol)
    return out
