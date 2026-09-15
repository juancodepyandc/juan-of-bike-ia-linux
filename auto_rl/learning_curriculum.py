"""Verifiable educational calculations, with whole skills held out from training.

This evaluates results of multi-step calculations, not free-form pedagogy.
"""
import json
import math
import random
from fractions import Fraction
from .curriculum import validate_tasks


def exercise(skill, rng):
    a, b, d = rng.randint(41, 193), rng.randint(13, 47), rng.randint(7, 19)
    if skill == 'equation':
        return f"Résous {b}(x − {a}) + {d}x = {(b+d)*d-b*a}. Donne x.", d
    if skill == 'fraction':
        f=Fraction(a,b)+Fraction(b,d)-Fraction(d,b+d)
        return f"Calcule {a}/{b} + {b}/{d} − {d}/{b+d}. Réponds par [numérateur, dénominateur] irréductibles.", [f.numerator,f.denominator]
    if skill == 'percentage':
        return f"Un stock de {a*10000} unités augmente de {b} %, puis diminue de {d} %. Quantité finale ?", a*(100+b)*(100-d)
    if skill == 'average':
        return f"Moyenne de {a*b}, {a*b+b}, {a*b+2*b}, {a*b+3*b}, {a*b+4*b} ?", a*b+2*b
    if skill == 'area':
        return f"Un rectangle de {a}×{b} cm comporte une découpe triangulaire de base {2*d} cm et hauteur {b} cm. Aire restante en cm² ?", (a-d)*b
    if skill == 'speed':
        return f"Une distance de {a*b} mètres est parcourue en {b} secondes. Vitesse en km/h ?", a*3.6
    if skill == 'units':
        return f"Convertis {a}.{b:02d} mètres en centimètres.", 100*a+b
    if skill == 'power':
        return f"Calcule {a}² − {b}².", a*a-b*b
    if skill == 'sequence':
        return f"Suite arithmétique de premier terme {a}, raison {b}. Valeur du terme numéro {d}, le premier porte le numéro 1 ?", a+(d-1)*b
    if skill == 'derivative':
        return f"f(x) = {a}x³ − {b}x² + {d}x. Calcule f'({d}).", 3*a*d*d-2*b*d+d
    if skill == 'probability':
        f=Fraction(a,a+b)*Fraction(a-1,a+b-1)
        return f"Une urne contient {a} boules rouges et {b} bleues. Deux tirages sans remise : probabilité de deux rouges, sous forme [numérateur, dénominateur] irréductibles ?", [f.numerator,f.denominator]
    if skill == 'energy':
        return f"Une puissance de {a} W est maintenue pendant {b} minutes, avec un rendement de {d} %. Énergie utile en joules ?", a*b*60*d/100
    if skill == 'ohm':
        return f"U = R×I. R = {a} ohms, I = {b} ampères. U en volts ?", a*b
    if skill == 'volume':
        return f"Volume d'un pavé de côtés {a}, {b}, {d} cm ? En cm³.", a*b*d
    if skill == 'gcd':
        return f"Plus grand diviseur commun de {a*d} et {b*d} ?", math.gcd(a*d,b*d)
    if skill == 'binary':
        return f"Convertis le nombre binaire {a*b:b} en entier décimal.", a*b
    if skill == 'median':
        xs=[a,a+b,a-b,a+2*b,a-2*b];rng.shuffle(xs)
        return f"Médiane de {xs} ?", a
    if skill == 'weighted':
        return f"Moyenne pondérée de {a} coefficient 1 et {a+3*b} coefficient 2 ?", a+2*b
    raise ValueError(skill)


def build_tasks(c):
    skills=['equation','fraction','percentage','average','area','speed','units','power',
            'sequence','derivative','probability','energy','ohm','volume','gcd','binary','median','weighted']
    rng=random.Random(c['seed']+4021)
    partition=random.Random(c.get('audit_partition_seed',c['seed'])+4021) if 'audit_partition_seed' in c else rng
    partition.shuffle(skills)
    tasks=[]
    for split,n,pool in [('train',c['train_tasks'],skills[:-8]),('audit',c['eval_tasks'],skills[-8:])]:
        for i in range(n):
            skill=pool[i%len(pool)]
            examples=[exercise(skill,rng) for _ in range(6 if c.get('curriculum_version') in {'radical-v2','radical-v3'} else 3)]
            tasks.append({'id':f'{split}_{skill}_{i:03d}','family':skill,'split':split,
                          'origin':'synthetic_verified_educational_oracle',
                          'prompt':'Résous ces trois exercices. Réponds uniquement en JSON {"answers":[résultat1,résultat2,résultat3]}, sans unités dans les valeurs. Respecte le format précisé par chaque exercice.\n'+ '\n'.join(f'{j+1}. {q}' for j,(q,_) in enumerate(examples)),
                          'expected_json':{'answers':[v for _,v in examples]}})
            if c.get('curriculum_version') in {'radical-v2','radical-v3'}:
                task=tasks[-1]
                numeric=[float(v) for _,v in examples if isinstance(v,(int,float))]
                task['expected_json']['verification']={'nombre_reponses':len(examples),'somme_numerique':round(sum(numeric),6)}
                task['prompt']=task['prompt'].replace('ces trois exercices','ces six exercices').replace('{"answers":[résultat1,résultat2,résultat3]}','{"answers":[un résultat par exercice],"verification":{"nombre_reponses":nombre,"somme_numerique":somme}}')
                task['prompt']+='\nLa somme de vérification porte uniquement sur les réponses qui sont des nombres, hors listes et chaînes ; arrondis-la à six décimales. Vérifie unités, ordre et cohérence de tous les résultats.'
                task.update(difficulty='multistep_with_cross_check',suite_version=c.get('curriculum_version','radical-v3'))
    validate_tasks(tasks,c)
    return tasks
