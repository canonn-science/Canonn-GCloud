import re
import requests
import numpy      
import math                                    
from numpy import sqrt, dot, cross                       
from numpy.linalg import norm                            
from urllib.parse import quote_plus
import json
from flask import escape
from os import getenv
import logging

#Distances of Merope and Col70
M=numpy.array([-78.59,-149.63,-340.53])
C=numpy.array([687.06,-362.53,-697.06])

#Placeholder for Origin
O=numpy.array([0,0,0])

radius=35
log=[]



#Units are the distances between Merope and Col70
unit = round(numpy.linalg.norm( M - C ),3)

def decode(  s ):
    """ Decodes the binary transcribed string """
    
    # Handle both hl and 01 encoding by normalizing into 01
    s = s.lower().replace( 'h', '0' ).replace( 'l', '1' )

    # Finally get rid of all extra spaces.
    s = s.replace( ' ', '' )

    # Any character other than 0 or 1 marks a segment difference.
    s = re.sub( '[^01]', ' ', s )

    # Ensure there's only one consecutive space ever.
    s = re.sub( ' +', ' ', s )
    s =s.strip()

    #print( s )
    log.append({ "decode":s})
    segments = s.split( ' ' )

    
    res = {}
    
    log.append({ "segments": segments})
    
    a = int( segments[ 0 ], 2 )

    if a == 0:
        log.append("a is zero")
        return { "lightyears": float(a)*unit, "numerator": a, "denominator": "n/a", "denominatorStatus": "ok", "precisionStatus": "ok", "status": True} 
        
    if len(segments) == 1:
        log.append("b is missing setting it to 1")
        b = 1    
    else:
        log.append("getting second segment")
        b = int( segments[ 1 ], 2 )

    #check the denominator is a fraction of 1000
    if 1000 % b != 0:
        dc="The denominator {} in ratio {}:{} is not a fraction of 1000".format(b,a,b)
    else:
        dc="ok"
    
    #check the results of the division no more than three decomal places
    val=str(float(a)/float(b))
    fraction=val.split('.')[1]
    if len(fraction) > 3:
        pc="The result of division  ({}) for {}/{} should only have 3 decimal places".format(val,a,b)
    else:
        pc = "ok"
    
    if pc == "ok" and dc == "ok":
        status=True
    else:
        status=False
        
    res= { "lightyears": (float(a) / float(b))*unit, "numerator": a, "denominator": b, "denominatorStatus": dc, "precisionStatus": pc, "status": status} 
    return res
    
    
def getCoordinates(system):
    try:
        url = 'https://www.edsm.net/api-v1/system?systemName={}&showCoordinates=1'      
        r = requests.get(url.format(system))
        s =  r.json()
        c=s.get("coords")
        return numpy.array([float(c.get("x")),float(c.get("y")),float(c.get("z"))])
    except:
        raise Exception("Unable to get system from EDSM")

def getSphere(c):
    try:
        url = 'https://www.edsm.net/api-v1/sphere-systems?x={}&y={}&z={}&radius={}&showCoordinates=1'
        r = requests.get(url.format(c[0],c[1],c[2],radius))
        s =  r.json()
        
        return s
    except:
        raise Exception("Unable to get system from EDSM")
        
# Find the intersection of three spheres                 
# P1,P2,P3 are the centers, r1,r2,r3 are the radii       
# Implementaton based on Wikipedia Trilateration article.                              
def trilaterate(P1,P2,P3,r1,r2,r3):                      
    temp1 = P2-P1                                        
    e_x = temp1/norm(temp1)                              
    temp2 = P3-P1                                        
    i = dot(e_x,temp2)                                   
    temp3 = temp2 - i*e_x                                
    e_y = temp3/norm(temp3)                              
    e_z = cross(e_x,e_y)                                 
    d = norm(P2-P1)                                      
    j = dot(e_y,temp2)                                   
    x = (r1*r1 - r2*r2 + d*d) / (2*d)                    
    y = (r1*r1 - r3*r3 -2*i*x + i*i + j*j) / (2*j)       
    temp4 = r1*r1 - x*x - y*y                            
    if temp4<0:                                          
        temp4=0
    z = sqrt(temp4)                                      
    p_12_a = P1 + x*e_x + y*e_y + z*e_z                  
    p_12_b = P1 + x*e_x + y*e_y - z*e_z                  
    return p_12_a,p_12_b        

def distance(sys1, sys2):
    return math.sqrt(math.pow((sys1[0] - sys2[0]), 2) + math.pow((sys1[1] - sys2[1]), 2) + math.pow((sys1[2] - sys2[2]), 2))        

def recalculate(PX,P1,P2,P3):
    d1=round(distance(PX,P1)/unit,3)
    d2=round(distance(PX,P2)/unit,3)
    d3=round(distance(PX,P3)/unit,3)

    dr1=d1*unit
    dr2=d2*unit
    dr3=d3*unit
    
    return trilaterate(P1,P2,P3,dr1,dr2,dr3)
        
def checkControl(r1,r2):


    d1=distance(r1[0],r2[0])
    d2=distance(r1[1],r2[1])

    return d1+d2        

def get_trilateration_result(O,r1,r2,r3,res):
    log.append("Trilaterating")
    results=trilaterate(M,O,C,r1,r2,r3)

    spread=round(distance(results[0],results[1]),2)
    res["trilateration"]={ "coords": [results[0].tolist(),results[1].tolist()], "spread": spread}            
    
    candidates=[]

    for r in results:
        candidates=candidates+getSphere(r)
            

    pick={ "name": "n/a", "control": 999999999, "distance": "999999999999", "x": 0, "y": 0,"z": 0, "matches": 0}

    # How do we pick candidatesi?
    # If we pick the closest system to the coordinates it might not be correct one
    # but we know the coordinates if the targets so we can calculate the position 
    # using thargoid rounding
    # We should get the same coordinates as fdev
    # so our pick should be the closest to the fdev calculation

    res["candidates"] = []
    clist= []

    log.append("picking candidates")

    for i in candidates:
        x = i.get("coords").get("x")
        y = i.get("coords").get("y")
        z = i.get("coords").get("z")


        PX=numpy.array([x,y,z])

        dm=round(distance(PX,M)/unit,3)*unit
        do=round(distance(PX,O)/unit,3)*unit
        dc=round(distance(PX,C)/unit,3)*unit

        matchCount=0 
        if dm - r1  == 0:
            matchCount=matchCount+1;
        if do - r2  == 0:
            matchCount=matchCount+1;
        if dc - r3  == 0:
            matchCount=matchCount+1;

        try: 
            control=recalculate(PX,M,O,C)
            cd=checkControl(results,control)
            

            clist.append({ "name": i.get("name"), "error": i.get("distance"), "control": round(cd,2), "matches": matchCount})

            matchPick=pick.get("matches") <= matchCount
            distancePick=pick.get("matches") == matchCount and pick.get("control") >= cd
            
            if matchPick or distancePick:
                pick["name"]=i.get("name") 
                pick["distance"]=i.get("distance") 
                pick["control"]=cd
                pick["x"]=i.get("coords").get("x") 
                pick["y"]=i.get("coords").get("y") 
                pick["z"]=i.get("coords").get("z") 
                pick["matches"]=matchCount

        except Exception as e:
            res["candidates"].append({ "name": i.get("name"), "msg": "Sphere's don't intersect", "realerror": str(e)})

    if pick.get("control") > 0:
        restext  = "Match is not proven transcript may be wrong"
    else:
        restext  = "Exact match"
        
    res["candidates"]=clist
    
    log.append("nearly finished triangulation")
            
    res["Result"]={ "name": pick.get("name"), "error": pick.get("distance"), "control": pick.get("control"), "matches": pick.get("matches"), "result": restext, "logs": log }
        

    return res 

    
def get_distance_result(O,r1,r2,r3,res):
    candidates=[]
    clist= []
    res["candidates"] = []
    pick={ "name": "n/a", "control": 999999999, "distance": "999999999999", "x": 0, "y": 0,"z": 0, "matches": 0}

    log.append("getting candidate spheres")
    if r1==0:
        candidates=candidates+getSphere(M)
    if r2==0:
        candidates=candidates+getSphere(O)        
    if r3==0:
        candidates=candidates+getSphere(C)                


    log.append("CANDIDATES")
    log.append(candidates)
    
    for i in candidates:
        log.append("Getting Coordinates")
        x = i.get("coords").get("x")
        y = i.get("coords").get("y")
        z = i.get("coords").get("z")

        PX=numpy.array([x,y,z])

        dm=round(distance(PX,M)/unit,3)*unit
        do=round(distance(PX,O)/unit,3)*unit
        dc=round(distance(PX,C)/unit,3)*unit

        if i.get("name") == 'Merope':
            log.append("Checking Matches")
            log.append([dm,do,dc])
            log.append([r1,r2,r3])

        matchCount=0 
        if dm - r1  == 0:
            matchCount=matchCount+1;
        if do - r2  == 0:
            matchCount=matchCount+1;
        if dc - r3  == 0:
            matchCount=matchCount+1;

        try: 
            #control=recalculate(PX,M,O,C)
            cd="n/a"
            log.append("appending to clist")
            clist.append({ "name": i.get("name"), "error": i.get("distance"), "control": cd, "matches": matchCount})

            matchPick=pick.get("matches") <= matchCount
            distancePick=pick.get("matches") == matchCount
            
            if matchPick or distancePick:
                pick["name"]=i.get("name") 
                pick["distance"]=i.get("distance") 
                pick["control"]=cd
                pick["x"]=i.get("coords").get("x") 
                pick["y"]=i.get("coords").get("y") 
                pick["z"]=i.get("coords").get("z") 
                pick["matches"]=matchCount

        except Exception as e:
            res["candidates"].append({ "name": i.get("name"), "msg": "Sphere's don't intersect", "realerror": str(e)})

    if pick.get("matches") < 3:
        restext  = "Match is not proven transcript may be wrong"
    else:
        restext  = "Exact match"
        
    res["candidates"]=clist
    
    
            
    res["Result"]={ "name": pick.get("name"), "error": pick.get("distance"), "control": pick.get("control"), "matches": pick.get("matches"), "result": restext, "logs": log }
        
    return res

    
def payload(request):
    
    # container for output
    res={}
    
    
    
    #CORS Requuest
    if request.method == 'OPTIONS':
        # Allows GET requests from any origin with the Content-Type
        # header and caches preflight response for an 3600s
        headers = {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'GET',
            'Access-Control-Allow-Headers': 'Content-Type',
            'Access-Control-Max-Age': '3600'
        }

        return ('', 204, headers)
    else:
        headers = {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*'
        }

    
    request_json = request.get_json(silent=True)
    request_args = request.args
    
    origin=request_args.get("origin")   
    message=request_args.get("message").replace(";","\n")

    try:
        O=getCoordinates(origin)    
        res["origin"]={ "name": origin, "coords": O.tolist()}
        
        decodes=[]
        messages=message.split("\n")
        log.append(message)
        log.append(messages)
        decodes.append(decode(messages[0]))
        decodes.append(decode(messages[1]))
        decodes.append(decode(messages[2]))
        
        log.append("finished decoding")

        decodes[0]["system"]="Merope"
        decodes[1]["system"]=origin
        decodes[2]["system"]="Col 70 Sector FY-N C21-3"

        log.append("enhanced decodes")

        res["decodes"]=decodes
        
        r1=decodes[0].get("lightyears")
        r2=decodes[1].get("lightyears")
        r3=decodes[2].get("lightyears")
        
        
        log.append({ "lightyears": [r1,r2,r3]})
        
        res["message"]=message

        #if any distances are zero then we can't triangulate
        # we can check if it is Merope
        
        log.append("WE SHOULD GET THIS FAR")
        if r1 == 0 or r2 == 0 or r3 == 0:
            log.append("getting distance result")
            res=get_distance_result(O,r1,r2,r3,res)
        else:
            log.append("getting trilateration result")
            res=get_trilateration_result(O,r1,r2,r3,res)


    except Exception as erm:
        log.append("GOT AN EXCEPTION")
        res["Result"]={ "name": "n/a", "error": "n/a", "control": "n/a", "matches": 0, "result": str(erm), "logs": log  }   
        
    headers = {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*'
    }

    return (json.dumps(res, indent=4),200,headers)