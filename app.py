from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import uvicorn

# ==========================================
# 1. LE MOTEUR DE CALCUL
# ==========================================
class MoteurHeritage:
    def __init__(self, total_biens, dette_funeraire=0.0, testament_active=False, madhhab="majorite"):
        self.total_biens = float(total_biens)
        self.dette_funeraire = float(dette_funeraire)
        base_apres_dettes = self.total_biens - self.dette_funeraire
        if base_apres_dettes < 0: base_apres_dettes = 0
        self.testament = (base_apres_dettes * (1.0/3.0)) if testament_active else 0.0
        self.actif_successoral = base_apres_dettes - self.testament
        if self.actif_successoral < 0: self.actif_successoral = 0
        self.madhhab = madhhab

    def format_montant(self, montant):
        montant_arrondi = round(montant)
        return f"{montant_arrondi:,.0f}".replace(",", " ") + " FCFA"

    def calculer(self, defunt_sexe, conjoint_vivant, nb_epouses, pere_vivant, mere_vivante, 
                 nb_fils, nb_filles, nb_petits_fils, nb_petites_filles, nb_grand_pere, 
                 nb_grand_mere_paternelle, nb_grand_mere_maternelle,
                 nb_freres_germains, nb_soeurs_germaines, 
                 nb_freres_consanguins, nb_soeurs_consanguines, nb_freres_uterins, nb_soeurs_uterines):
        
        condition_enfant = "a un enfant" if (nb_fils > 0 or nb_filles > 0 or nb_petits_fils > 0 or nb_petites_filles > 0) else "n'a pas d'enfant"
        exclusions = []
        
        a_fils = nb_fils > 0
        a_fille = nb_filles > 0
        a_petit_fils = nb_petits_fils > 0
        a_petite_fille = nb_petites_filles > 0
        a_descendant = (a_fils or a_fille or a_petit_fils or a_petite_fille)
        a_frere_germain = nb_freres_germains > 0
        a_frere_consanguin = nb_freres_consanguins > 0

        # ==========================================
        # GESTION DES EXCLUSIONS (AL-HAJB)
        # ==========================================
        
        if mere_vivante:
            if nb_grand_mere_paternelle > 0:
                exclusions.append("Grand-mère paternelle exclue par la présence de la mère.")
                nb_grand_mere_paternelle = 0
            if nb_grand_mere_maternelle > 0:
                exclusions.append("Grand-mère maternelle exclue par la présence de la mère.")
                nb_grand_mere_maternelle = 0
            
        if pere_vivant:
            if nb_grand_pere > 0:
                exclusions.append("Grand-père paternel exclu par la présence du père.")
                nb_grand_pere = 0
            if nb_grand_mere_paternelle > 0:
                exclusions.append("Grand-mère paternelle exclue par la présence du père.")
                nb_grand_mere_paternelle = 0
            
        if a_fils and (a_petit_fils or a_petite_fille):
            exclusions.append("Petit(s)-enfant(s) exclu(s) par la présence d'un fils vivant.")
            nb_petits_fils = 0; nb_petites_filles = 0
            a_petit_fils = False; a_petite_fille = False

        if a_descendant:
            if nb_freres_germains > 0 or nb_soeurs_germaines > 0:
                exclusions.append("Frère(s)/Sœur(s) germain(s) exclus par la présence d'un descendant.")
                nb_freres_germains = 0; nb_soeurs_germaines = 0
            if nb_freres_consanguins > 0 or nb_soeurs_consanguines > 0:
                exclusions.append("Frère(s)/Sœur(s) consanguin(s) exclus par la présence d'un descendant.")
                nb_freres_consanguins = 0; nb_soeurs_consanguines = 0
            if nb_freres_uterins > 0 or nb_soeurs_uterines > 0:
                exclusions.append("Frère(s)/Sœur(s) utérin(s) exclus par la présence d'un descendant.")
                nb_freres_uterins = 0; nb_soeurs_uterines = 0
            
        if pere_vivant or nb_grand_pere > 0:
            if nb_freres_germains > 0 or nb_soeurs_germaines > 0:
                exclusions.append("Frère(s)/Sœur(s) germain(s) exclus par la présence d'un père ou grand-père.")
                nb_freres_germains = 0; nb_soeurs_germaines = 0
            if nb_freres_consanguins > 0 or nb_soeurs_consanguines > 0:
                exclusions.append("Frère(s)/Sœur(s) consanguin(s) exclus par la présence d'un père ou grand-père.")
                nb_freres_consanguins = 0; nb_soeurs_consanguines = 0
            if nb_freres_uterins > 0 or nb_soeurs_uterines > 0:
                exclusions.append("Frère(s)/Sœur(s) utérin(s) exclus par la présence d'un père ou grand-père.")
                nb_freres_uterins = 0; nb_soeurs_uterines = 0

        if a_frere_germain or nb_soeurs_germaines > 0:
            if nb_freres_consanguins > 0 or nb_soeurs_consanguines > 0:
                exclusions.append("Frère(s)/Sœur(s) consanguin(s) exclus par la présence de germains.")
                nb_freres_consanguins = 0; nb_soeurs_consanguines = 0
        if a_frere_consanguin or nb_soeurs_consanguines > 0:
            if nb_freres_uterins > 0 or nb_soeurs_uterines > 0:
                exclusions.append("Frère(s)/Sœur(s) utérin(s) exclus par la présence de consanguins.")
                nb_freres_uterins = 0; nb_soeurs_uterines = 0

        a_descendant = (nb_fils > 0 or nb_filles > 0 or nb_petits_fils > 0 or nb_petites_filles > 0)
        a_fratrie = (nb_freres_germains + nb_soeurs_germaines + nb_freres_consanguins + nb_soeurs_consanguines + nb_freres_uterins + nb_soeurs_uterines) > 0
        cas_kalala = (not a_descendant) and (not pere_vivant) and (nb_grand_pere == 0)

        parts = {}

        # 1. Le Conjoint
        if conjoint_vivant:
            if defunt_sexe == "homme" and nb_epouses > 0:
                total_epouses = 1.0/8.0 if a_descendant else 1.0/4.0
                part_fixe = "1/8 (12.5%)" if a_descendant else "1/4 (25%)"
                detail_str = f"L'épouse a droit à {part_fixe}. Étant {nb_epouses}, elles se partagent cette fraction."
                parts["Epouse(s)"] = {"fraction": total_epouses, "fraction_fixe": total_epouses, "fraction_asaba": 0.0, "fraction_radd": 0.0, "nombre": nb_epouses, "detail": detail_str, "source": "Sourate An-Nisa (4:12)"}
            elif defunt_sexe == "femme":
                total_mari = 1.0/4.0 if a_descendant else 1.0/2.0
                part_fixe = "1/4 (25%)" if a_descendant else "1/2 (50%)"
                detail_str = f"Le mari a droit à {part_fixe}."
                parts["Mari"] = {"fraction": total_mari, "fraction_fixe": total_mari, "fraction_asaba": 0.0, "fraction_radd": 0.0, "nombre": 1, "detail": detail_str, "source": "Sourate An-Nisa (4:12)"}

        # 2. Les Ascendants (Mère, Grand-mères, Père, Grand-père)
        if mere_vivante:
            if a_descendant or (a_fratrie and not a_descendant):
                parts["Mere"] = {"fraction": 1.0/6.0, "fraction_fixe": 1.0/6.0, "fraction_asaba": 0.0, "fraction_radd": 0.0, "nombre": 1, "detail": "La mère hérite de 1/6 (16.67%).", "source": "Sourate An-Nisa (4:11)"}
            else:
                parts["Mere"] = {"fraction": 1.0/3.0, "fraction_fixe": 1.0/3.0, "fraction_asaba": 0.0, "fraction_radd": 0.0, "nombre": 1, "detail": "La mère hérite de 1/3 (33.33%).", "source": "Sourate An-Nisa (4:11)"}
        else:
            total_grands_meres = nb_grand_mere_paternelle + nb_grand_mere_maternelle
            if total_grands_meres > 0:
                fraction_gm = 1.0/6.0
                fraction_individuelle_gm = fraction_gm / total_grands_meres
                
                if nb_grand_mere_paternelle > 0:
                    parts["Grand-mère paternelle"] = {"fraction": fraction_individuelle_gm * nb_grand_mere_paternelle, "fraction_fixe": fraction_individuelle_gm * nb_grand_mere_paternelle, "fraction_asaba": 0.0, "fraction_radd": 0.0, "nombre": nb_grand_mere_paternelle, "detail": f"La grand-mère paternelle hérite de 1/6 partagé.", "source": "Sunnah - Hadith sur la grand-mère"}
                if nb_grand_mere_maternelle > 0:
                    parts["Grand-mère maternelle"] = {"fraction": fraction_individuelle_gm * nb_grand_mere_maternelle, "fraction_fixe": fraction_individuelle_gm * nb_grand_mere_maternelle, "fraction_asaba": 0.0, "fraction_radd": 0.0, "nombre": nb_grand_mere_maternelle, "detail": f"La grand-mère maternelle hérite de 1/6 partagé.", "source": "Sunnah - Hadith sur la grand-mère"}

        if pere_vivant:
            if a_fils or a_petit_fils:
                parts["Pere"] = {"fraction": 1.0/6.0, "fraction_fixe": 1.0/6.0, "fraction_asaba": 0.0, "fraction_radd": 0.0, "nombre": 1, "detail": "Le père hérite de 1/6 (16.67%).", "source": "Sourate An-Nisa (4:11)"}
            elif (a_fille or a_petite_fille) and not a_fils and not a_petit_fils:
                parts["Pere"] = {"fraction": 1.0/6.0, "fraction_fixe": 1.0/6.0, "fraction_asaba": 0.0, "fraction_radd": 0.0, "nombre": 1, "detail": "Le père prend 1/6 fixe + le résiduel (Asaba).", "source": "Sourate An-Nisa (4:11)"}
        elif nb_grand_pere > 0:
            if a_fils or a_petit_fils:
                parts["Grand-pere"] = {"fraction": 1.0/6.0, "fraction_fixe": 1.0/6.0, "fraction_asaba": 0.0, "fraction_radd": 0.0, "nombre": 1, "detail": "Le grand-père paternel hérite de 1/6 (16.67%).", "source": "Sourate An-Nisa (4:11) - Analogie"}
            elif (a_fille or a_petite_fille) and not a_fils and not a_petit_fils:
                parts["Grand-pere"] = {"fraction": 1.0/6.0, "fraction_fixe": 1.0/6.0, "fraction_asaba": 0.0, "fraction_radd": 0.0, "nombre": 1, "detail": "Le grand-père paternel prend 1/6 fixe + le résiduel (Asaba).", "source": "Sourate An-Nisa (4:11) - Analogie"}

        # 3. Les Filles & Petites-filles (CORRIGÉ)
        if not a_fils:
            if a_fille:
                # Il y a une ou plusieurs filles directes
                if nb_filles == 1:
                    parts["Fille(s)"] = {"fraction": 1.0/2.0, "fraction_fixe": 1.0/2.0, "fraction_asaba": 0.0, "fraction_radd": 0.0, "nombre": 1, "detail": "Fille unique sans frère : prend 1/2 (50%).", "source": "Sourate An-Nisa (4:11)"}
                    # CORRECTION : La petite-fille ne prend 1/6 QUE s'il n'y a pas de petit-fils
                    if a_petite_fille and not a_petit_fils:
                        parts["Petite-fille(s)"] = {"fraction": 1.0/6.0, "fraction_fixe": 1.0/6.0, "fraction_asaba": 0.0, "fraction_radd": 0.0, "nombre": nb_petites_filles, "detail": "Petite(s)-fille(s) complète(nt) le 2/3, prend 1/6.", "source": "Sourate An-Nisa (4:11) - Représentation"}
                else:
                    parts["Fille(s)"] = {"fraction": 2.0/3.0, "fraction_fixe": 2.0/3.0, "fraction_asaba": 0.0, "fraction_radd": 0.0, "nombre": nb_filles, "detail": "Plusieurs filles prennent le 2/3 max, excluant les petites-filles.", "source": "Sourate An-Nisa (4:11)"}
                    if a_petite_fille:
                        exclusions.append("Petite-fille(s) exclue(s) par la présence de 2 filles ou plus.")
                        nb_petites_filles = 0
                        a_petite_fille = False
            else:
                # Pas de fille directe, on regarde les petites-filles
                if a_petite_fille:
                    if nb_petites_filles == 1:
                        parts["Petite-fille(s)"] = {"fraction": 1.0/2.0, "fraction_fixe": 1.0/2.0, "fraction_asaba": 0.0, "fraction_radd": 0.0, "nombre": 1, "detail": "Petite-fille unique sans père : prend 1/2.", "source": "Sourate An-Nisa (4:11) - Représentation"}
                    else:
                        parts["Petite-fille(s)"] = {"fraction": 2.0/3.0, "fraction_fixe": 2.0/3.0, "fraction_asaba": 0.0, "fraction_radd": 0.0, "nombre": nb_petites_filles, "detail": "Plusieurs petites-filles : se partagent 2/3.", "source": "Sourate An-Nisa (4:11) - Représentation"}

        # 4. Frères et Sœurs Utérins
        total_uterins = nb_freres_uterins + nb_soeurs_uterines
        if cas_kalala and total_uterins > 0:
            if total_uterins == 1:
                parts["Frere/Soeur Utérin(s)"] = {"fraction": 1.0/6.0, "fraction_fixe": 1.0/6.0, "fraction_asaba": 0.0, "fraction_radd": 0.0, "nombre": 1, "detail": "Un seul utérin : prend 1/6 (16.67%).", "source": "Sourate An-Nisa (4:12)"}
            else:
                parts["Frere/Soeur Utérin(s)"] = {"fraction": 1.0/3.0, "fraction_fixe": 1.0/3.0, "fraction_asaba": 0.0, "fraction_radd": 0.0, "nombre": total_uterins, "detail": "Plusieurs utérins : se partagent 1/3 (33.33%).", "source": "Sourate An-Nisa (4:12)"}

        # 5. Sœurs Germanines et Consanguines seules
        if cas_kalala and not a_descendant:
            if a_frere_germain == False and a_frere_consanguin == False:
                total_soeurs = nb_soeurs_germaines + nb_soeurs_consanguines
                if total_soeurs == 1:
                    label = "Soeur germaine" if nb_soeurs_germaines == 1 else "Soeur consanguine"
                    parts[label] = {"fraction": 1.0/2.0, "fraction_fixe": 1.0/2.0, "fraction_asaba": 0.0, "fraction_radd": 0.0, "nombre": 1, "detail": label + " unique : prend 1/2 (50%).", "source": "Sourate An-Nisa (4:176)"}

        # ==========================================
        # CALCUL DU RÉSIDUEL (ASABA)
        # ==========================================
        total_fixe = sum(v["fraction"] for v in parts.values())
        residuel = 1.0 - total_fixe
        asaba_existe = False

        if a_fils and residuel > 0:
            parts_totales_enfants = (nb_fils * 2) + nb_filles
            part_individuelle = residuel / parts_totales_enfants
            parts["Fils(s)"] = {"fraction": nb_fils * (part_individuelle * 2), "fraction_fixe": 0.0, "fraction_asaba": nb_fils * (part_individuelle * 2), "fraction_radd": 0.0, "nombre": nb_fils, "detail": "Les fils prennent le résiduel (Asaba).", "source": "Sourate An-Nisa (4:11)"}
            if nb_filles > 0:
                parts["Fille(s)"] = {"fraction": nb_filles * part_individuelle, "fraction_fixe": 0.0, "fraction_asaba": nb_filles * part_individuelle, "fraction_radd": 0.0, "nombre": nb_filles, "detail": "Les filles prennent le résiduel (Asaba) avec le frère.", "source": "Sourate An-Nisa (4:11)"}
            residuel = 0.0; asaba_existe = True
            
        elif a_petit_fils and residuel > 0:
            parts_totales = (nb_petits_fils * 2) + nb_petites_filles
            part_individuelle = residuel / parts_totales
            parts["Petit-fils(s)"] = {"fraction": nb_petits_fils * (part_individuelle * 2), "fraction_fixe": 0.0, "fraction_asaba": nb_petits_fils * (part_individuelle * 2), "fraction_radd": 0.0, "nombre": nb_petits_fils, "detail": "Les petits-fils prennent le résiduel (Asaba) par représentation.", "source": "Sourate An-Nisa (4:11) - Représentation"}
            if nb_petites_filles > 0:
                parts["Petite-fille(s)"] = {"fraction": nb_petites_filles * part_individuelle, "fraction_fixe": 0.0, "fraction_asaba": nb_petites_filles * part_individuelle, "fraction_radd": 0.0, "nombre": nb_petites_filles, "detail": "Les petites-filles prennent le résiduel (Asaba) avec le petit-fils.", "source": "Sourate An-Nisa (4:11) - Représentation"}
            residuel = 0.0; asaba_existe = True
            
        elif pere_vivant and not a_fils and not a_petit_fils and residuel > 0:
            parts["Pere"]["fraction"] += residuel
            parts["Pere"]["fraction_asaba"] += residuel
            residuel = 0.0; asaba_existe = True
            
        elif nb_grand_pere > 0 and not a_fils and not a_petit_fils and residuel > 0:
            parts["Grand-pere"]["fraction"] += residuel
            parts["Grand-pere"]["fraction_asaba"] += residuel
            residuel = 0.0; asaba_existe = True
            
        elif cas_kalala:
            if a_frere_germain and residuel > 0:
                parts_totales = (nb_freres_germains * 2) + nb_soeurs_germaines
                part_ind = residuel / parts_totales
                parts["Frere(s) germain(s)"] = {"fraction": nb_freres_germains * (part_ind * 2), "fraction_fixe": 0.0, "fraction_asaba": nb_freres_germains * (part_ind * 2), "fraction_radd": 0.0, "nombre": nb_freres_germains, "detail": "Frères germains prennent le résiduel (Asaba).", "source": "Sourate An-Nisa (4:176)"}
                if nb_soeurs_germaines > 0:
                    parts["Soeur(s) germaine(s)"] = {"fraction": nb_soeurs_germaines * part_ind, "fraction_fixe": 0.0, "fraction_asaba": nb_soeurs_germaines * part_ind, "fraction_radd": 0.0, "nombre": nb_soeurs_germaines, "detail": "Sœurs germanines prennent le résiduel (Asaba).", "source": "Sourate An-Nisa (4:176)"}
                residuel = 0.0; asaba_existe = True
            elif a_frere_consanguin and residuel > 0:
                parts_totales = (nb_freres_consanguins * 2) + nb_soeurs_consanguines
                part_ind = residuel / parts_totales
                parts["Frere(s) consanguin(s)"] = {"fraction": nb_freres_consanguins * (part_ind * 2), "fraction_fixe": 0.0, "fraction_asaba": nb_freres_consanguins * (part_ind * 2), "fraction_radd": 0.0, "nombre": nb_freres_consanguins, "detail": "Frères consanguins prennent le résiduel (Asaba).", "source": "Sourate An-Nisa (4:176)"}
                if nb_soeurs_consanguines > 0:
                    parts["Soeur(s) consanguine(s)"] = {"fraction": nb_soeurs_consanguines * part_ind, "fraction_fixe": 0.0, "fraction_asaba": nb_soeurs_consanguines * part_ind, "fraction_radd": 0.0, "nombre": nb_soeurs_consanguines, "detail": "Sœurs consanguines prennent le résiduel (Asaba).", "source": "Sourate An-Nisa (4:176)"}
                residuel = 0.0; asaba_existe = True

        # ==========================================
        # AWL ET RADD
        # ==========================================
        somme_totale = sum(v["fraction"] for v in parts.values())
        epsilon = 1e-9
        info_awl = None
        info_radd = None

        if somme_totale > 1.0 + epsilon:
            info_awl = f"La somme des parts fixes était de {somme_totale * 100:.2f}%. Le Al-Awl a été appliqué."
            multiplicateur = 1.0 / somme_totale
            for k in parts:
                parts[k]["fraction"] *= multiplicateur
                parts[k]["fraction_fixe"] *= multiplicateur
                parts[k]["fraction_asaba"] *= multiplicateur
                parts[k]["detail"] += " | ATTENTION : Al-Awl appliqué."
            somme_totale = sum(v["fraction"] for v in parts.values())
            
        elif somme_totale < 1.0 - epsilon and not asaba_existe:
            surplus = 1.0 - somme_totale
            if self.madhhab == "hanafi":
                info_radd = f"Il restait un surplus de {surplus * 100:.2f}%. Le Al-Radd a été appliqué. Selon l'école HANAFI, le conjoint et le grand-père participent au Radd."
                heritiers_radd = {k: v for k, v in parts.items() if k not in ["Frere/Soeur Utérin(s)"]}
            else:
                ecole_nom = "Maliki" if self.madhhab == "maliki" else ("Chafi'i" if self.madhhab == "chafii" else "Hanbali")
                info_radd = f"Il restait un surplus de {surplus * 100:.2f}%. Le Al-Radd a été appliqué. Selon l'école {ecole_nom} (et la majorité), le conjoint NE participe PAS au Radd."
                heritiers_radd = {k: v for k, v in parts.items() if k not in ["Epouse(s)", "Mari", "Frere/Soeur Utérin(s)"]}
            
            total_fixe_radd = sum(v["fraction"] for v in heritiers_radd.values())
            if total_fixe_radd > 0:
                for k in heritiers_radd:
                    proportion = parts[k]["fraction"] / total_fixe_radd
                    radd_amount = surplus * proportion
                    parts[k]["fraction"] += radd_amount
                    parts[k]["fraction_radd"] += radd_amount
                    parts[k]["detail"] += " | ATTENTION : Al-Radd appliqué."
                somme_totale = sum(v["fraction"] for v in parts.values())

        # ==========================================
        # FORMATAGE
        # ==========================================
        resultats = []
        for heritier, data in parts.items():
            fraction_normalisee = data["fraction"] / somme_totale if somme_totale > 0 else 0
            montant_groupe = fraction_normalisee * self.actif_successoral
            montant_individuel = montant_groupe / data["nombre"] if data["nombre"] > 0 else 0
            
            fixe_pct = (data["fraction_fixe"] / somme_totale) * 100 if somme_totale > 0 else 0
            asaba_pct = (data["fraction_asaba"] / somme_totale) * 100 if somme_totale > 0 else 0
            radd_pct = (data["fraction_radd"] / somme_totale) * 100 if somme_totale > 0 else 0
            
            parts_list = []
            if fixe_pct > epsilon: parts_list.append(f"{fixe_pct:.2f}% (Fixe)")
            if asaba_pct > epsilon: parts_list.append(f"{asaba_pct:.2f}% (Asaba)")
            if radd_pct > epsilon: parts_list.append(f"{radd_pct:.2f}% (Radd)")
            
            part_detail_str = " + ".join(parts_list) if parts_list else "0.00 %"
            
            resultats.append({
                "heritier": heritier,
                "nombre": data["nombre"],
                "part_pourcentage": f"{fraction_normalisee * 100:.2f} %",
                "part_detail": part_detail_str,
                "montant_total": self.format_montant(montant_groupe),
                "montant_individuel": self.format_montant(montant_individuel),
                "detail": data["detail"],
                "source": data["source"]
            })
            
        return {"resultats": resultats, "exclusions": exclusions, "info_awl": info_awl, "info_radd": info_radd}

# ==========================================
# 2. L'API ET L'INTERFACE WEB
# ==========================================
app = FastAPI()

class CalculRequest(BaseModel):
    total_biens: float
    dettes: float = 0.0
    testament_active: bool = False
    madhhab: str = "majorite"
    sexe_defunt: str
    conjoint: bool
    nb_epouses: int = 0
    pere: bool
    mere: bool
    nb_grand_pere: int = 0
    nb_grand_mere_paternelle: int = 0
    nb_grand_mere_maternelle: int = 0
    fils: int
    filles: int
    nb_petits_fils: int = 0
    nb_petites_filles: int = 0
    freres: int
    soeurs: int
    freres_cons: int = 0
    soeurs_cons: int = 0
    freres_uter: int = 0
    soeurs_uter: int = 0

@app.post("/api/calculer")
def api_calculer(req: CalculRequest):
    moteur = MoteurHeritage(req.total_biens, req.dettes, req.testament_active, req.madhhab)
    data = moteur.calculer(
        req.sexe_defunt, req.conjoint, req.nb_epouses, req.pere, req.mere, 
        req.fils, req.filles, req.nb_petits_fils, req.nb_petites_filles, req.nb_grand_pere, 
        req.nb_grand_mere_paternelle, req.nb_grand_mere_maternelle,
        req.freres, req.soeurs, req.freres_cons, req.soeurs_cons, req.freres_uter, req.soeurs_uter
    )
    return {
        "total_biens": moteur.format_montant(req.total_biens),
        "dettes": moteur.format_montant(req.dettes),
        "testament": moteur.format_montant(moteur.testament),
        "actif_successoral": moteur.format_montant(moteur.actif_successoral),
        "heritiers": data["resultats"], 
        "exclusions": data["exclusions"],
        "info_awl": data["info_awl"],
        "info_radd": data["info_radd"]
    }

HTML_PAGE = """
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <title>Calcul des Parts Successorales Islamiques</title>
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; max-width: 900px; margin: 20px auto; padding: 20px; background-color: #f4f7f6; }
        h2 { color: #2c3e50; text-align: center; border-bottom: 2px solid #2c3e50; padding-bottom: 10px; }
        h3 { color: #34495e; margin-top: 20px; border-bottom: 1px solid #bdc3c7; padding-bottom: 5px; font-size: 18px; }
        .form-group { margin-bottom: 15px; }
        label { display: block; margin-bottom: 5px; font-weight: bold; color: #34495e; }
        input, select { width: 100%; padding: 8px; box-sizing: border-box; border: 1px solid #bdc3c7; border-radius: 4px; }
        .row { display: flex; gap: 15px; }
        .row .form-group { flex: 1; }
        button { background: #2980b9; color: white; padding: 12px 15px; border: none; cursor: pointer; width: 100%; border-radius: 4px; font-size: 16px; font-weight: bold; margin-top: 10px;}
        button:hover { background: #3498db; }
        .btn-action { width: auto; padding: 6px 10px; font-size: 13px; margin-top: 0; border-radius: 3px; margin-right: 5px;}
        .btn-desc { background: #8e44ad; width: auto; margin-bottom: 20px; display: inline-block; }
        .btn-desc:hover { background: #9b59b6; }
        .btn-print { background: #27ae60; width: auto; display: inline-block; margin-top: 20px; }
        .btn-print:hover { background: #2ecc71; }
        .result { margin-top: 20px; border: 1px solid #2c3e50; padding: 15px; background: white; border-radius: 5px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        table { width: 100%; border-collapse: collapse; margin-top: 15px; }
        th, td { border: 1px solid #ddd; padding: 10px; text-align: center; }
        th { background-color: #2c3e50; color: white; }
        #epouses_div { display: none; }
        .exclusions-box { background: #ffece6; border: 1px solid #e67e22; padding: 15px; border-radius: 5px; margin-top: 15px; }
        .exclusions-box h4 { margin: 0 0 10px 0; color: #d35400; }
        .exclusions-box ul { margin: 0; padding-left: 20px; }
        .info-box { background: #e8f6f3; border: 1px solid #16a085; padding: 15px; border-radius: 5px; margin-top: 15px; }
        .info-box h4 { margin: 0 0 10px 0; color: #1abc9c; }
        .awl-box { background: #ffdddd; border: 1px solid #e74c3c; padding: 15px; border-radius: 5px; margin-top: 15px; }
        .awl-box h4 { margin: 0; color: #c0392b; }
        .madhhab-box { background: #fdf6e3; border: 1px solid #f39c12; padding: 15px; border-radius: 5px; margin-bottom: 20px; }
        .madhhab-box label { color: #d35400; }
        
        .modal-overlay { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.6); justify-content: center; align-items: center; z-index: 1000; }
        .modal-content { background: white; padding: 25px; border-radius: 8px; width: 80%; max-width: 600px; position: relative; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
        .modal-title { margin-top: 0; color: #2c3e50; border-bottom: 1px solid #eee; padding-bottom: 10px; }
        .modal-body { font-size: 15px; color: #333; line-height: 1.6; white-space: pre-wrap; }
        .modal-close { position: absolute; top: 15px; right: 15px; background: #e74c3c; color: white; border: none; border-radius: 50%; width: 30px; height: 30px; font-size: 16px; cursor: pointer; display: flex; justify-content: center; align-items: center; padding: 0;}

        @media print {
            body { background: white; }
            .btn-desc, .btn-print, .form-group, button, h3, .madhhab-box { display: none !important; }
            .result { box-shadow: none; border: 1px solid #000; }
            .no-print { display: none !important; }
        }
    </style>
</head>
<body>
    <h2>Calculateur d'Héritage Islamique</h2>
    
    <button class="btn-desc" onclick="showDescription()">Description de l'exercice</button>

    <div class="madhhab-box">
        <label>École de Jurisprudence (Madhhab) :</label>
        <select id="madhhab" onchange="updateMadhhabInfo()">
            <option value="majorite">Majorité (Maliki, Chafi'i, Hanbali)</option>
            <option value="hanafi">École Hanafi</option>
        </select>
        <p id="madhhab_info" style="font-size: 13px; margin-top: 8px; color: #7f8c8d; font-style: italic;">
            Selon la majorité, le conjoint ne participe pas au Al-Radd (retour du surplus).
        </p>
    </div>

    <h3>Finances</h3>
    <div class="row">
        <div class="form-group">
            <label>Total des Biens (FCFA)</label>
            <input type="number" id="total_biens" value="1000000">
        </div>
        <div class="form-group">
            <label>Dettes à payer (FCFA)</label>
            <input type="number" id="dettes" value="0">
        </div>
        <div class="form-group">
            <label>Testament (1/3 auto) ?</label>
            <input type="checkbox" id="testament_checkbox" style="width: auto; margin-top: 12px;">
        </div>
    </div>

    <h3>Conjoint & Parents</h3>
    <div class="row">
        <div class="form-group">
            <label>Sexe du défunt</label>
            <select id="sexe_defunt" onchange="updateConjointUI()">
                <option value="homme">Homme</option>
                <option value="femme">Femme</option>
            </select>
        </div>
        <div class="form-group">
            <label id="conjoint_label">Épouse(s) vivante(s) ?</label>
            <input type="checkbox" id="conjoint" checked onchange="updateConjointUI()" style="width: auto; margin-top: 12px;">
        </div>
        <div class="form-group" id="epouses_div">
            <label>Nombre d'épouses</label>
            <input type="number" id="nb_epouses" value="1" min="1" max="4">
        </div>
        <div class="form-group">
            <label>Père vivant ?</label>
            <input type="checkbox" id="pere" checked style="width: auto; margin-top: 12px;">
        </div>
        <div class="form-group">
            <label>Mère vivante ?</label>
            <input type="checkbox" id="mere" checked style="width: auto; margin-top: 12px;">
        </div>
    </div>

    <h3>Grands-parents (Si parents absents)</h3>
    <div class="row">
        <div class="form-group">
            <label>Grand-père paternel vivant ?</label>
            <input type="checkbox" id="grand_pere" style="width: auto; margin-top: 12px;">
        </div>
        <div class="form-group">
            <label>Grand-mère paternelle vivante ?</label>
            <input type="checkbox" id="grand_mere_pat" style="width: auto; margin-top: 12px;">
        </div>
        <div class="form-group">
            <label>Grand-mère maternelle vivante ?</label>
            <input type="checkbox" id="grand_mere_mat" style="width: auto; margin-top: 12px;">
        </div>
    </div>

    <h3>Descendants</h3>
    <div class="row">
        <div class="form-group">
            <label>Nombre de fils</label>
            <input type="number" id="fils" value="0" min="0">
        </div>
        <div class="form-group">
            <label>Nombre de filles</label>
            <input type="number" id="filles" value="1" min="0">
        </div>
    </div>
    <div class="row">
        <div class="form-group">
            <label>Petits-fils (du fils décédé)</label>
            <input type="number" id="petits_fils" value="0" min="0">
        </div>
        <div class="form-group">
            <label>Petites-filles (du fils décédé)</label>
            <input type="number" id="petites_filles" value="0" min="0">
        </div>
    </div>

    <h3>Fratrie (Germains - Même père et mère)</h3>
    <div class="row">
        <div class="form-group">
            <label>Frères germains</label>
            <input type="number" id="freres" value="0" min="0">
        </div>
        <div class="form-group">
            <label>Sœurs germaines</label>
            <input type="number" id="soeurs" value="0" min="0">
        </div>
    </div>

    <h3>Fratrie (Consanguins - Même père, mère différente)</h3>
    <div class="row">
        <div class="form-group">
            <label>Frères consanguins</label>
            <input type="number" id="freres_cons" value="0" min="0">
        </div>
        <div class="form-group">
            <label>Sœurs consanguines</label>
            <input type="number" id="soeurs_cons" value="0" min="0">
        </div>
    </div>

    <h3>Fratrie (Utérins - Même mère, père différent)</h3>
    <div class="row">
        <div class="form-group">
            <label>Frères utérins</label>
            <input type="number" id="freres_uter" value="0" min="0">
        </div>
        <div class="form-group">
            <label>Sœurs utérines</label>
            <input type="number" id="soeurs_uter" value="0" min="0">
        </div>
    </div>
    
    <button onclick="calculer()">Calculer l'Héritage</button>

    <div class="result" id="resultats" style="display:none;"></div>

    <div class="modal-overlay" id="modal-overlay" onclick="closeModal()">
        <div class="modal-content" onclick="event.stopPropagation()">
            <button class="modal-close" onclick="closeModal()">X</button>
            <h3 class="modal-title" id="modal-title"></h3>
            <p class="modal-body" id="modal-body"></p>
        </div>
    </div>

    <script>
        function updateConjointUI() {
            const sexe = document.getElementById('sexe_defunt').value;
            const conjointLabel = document.getElementById('conjoint_label');
            const epousesDiv = document.getElementById('epouses_div');
            
            if (sexe === 'homme') {
                conjointLabel.innerText = 'Épouse(s) vivante(s) ?';
                epousesDiv.style.display = 'block';
            } else {
                conjointLabel.innerText = 'Mari vivant ?';
                epousesDiv.style.display = 'none';
            }
        }
        updateConjointUI();

        function updateMadhhabInfo() {
            const madhhab = document.getElementById('madhhab').value;
            const info = document.getElementById('madhhab_info');
            if (madhhab === 'hanafi') {
                info.innerText = "Selon l'école Hanafi, le conjoint ET le grand-père participent au Al-Radd (retour du surplus).";
            } else {
                info.innerText = "Selon la majorité, le conjoint ne participe pas au Al-Radd (retour du surplus).";
            }
        }
        updateMadhhabInfo();

        function showModal(title, body) {
            document.getElementById('modal-title').innerText = title;
            document.getElementById('modal-body').innerText = body;
            document.getElementById('modal-overlay').style.display = 'flex';
        }
        
        function closeModal() {
            document.getElementById('modal-overlay').style.display = 'none';
        }

        function showDescription() {
            let title = "Description de l'exercice";
            let body = "L'héritage en Islam (Farâ'id) obéit à des règles mathématiques strictes. L'actif successoral est réparti en priorité aux ayants droit à parts fixes (Coran). S'il reste un surplus, il va aux héritiers par filiation mâle (Asaba). ";
            body += "Si le total des parts fixes dépasse 100%, le Al-Awl réduit proportionnellement les parts. S'il reste un surplus sans héritier mâle, le Al-Radd le redistribue aux ayants droit fixes (sauf le conjoint selon la majorité).";
            showModal(title, body);
        }

        let heritiersData = [];
        async function calculer() {
            const sexe = document.getElementById('sexe_defunt').value;
            const conjoint = document.getElementById('conjoint').checked;
            let nb_epouses = 0;
            if (sexe === 'homme' && conjoint) {
                nb_epouses = parseInt(document.getElementById('nb_epouses').value) || 1;
            }

            const data = {
                total_biens: parseFloat(document.getElementById('total_biens').value),
                dettes: parseFloat(document.getElementById('dettes').value),
                testament_active: document.getElementById('testament_checkbox').checked,
                madhhab: document.getElementById('madhhab').value,
                sexe_defunt: sexe,
                conjoint: conjoint,
                nb_epouses: nb_epouses,
                pere: document.getElementById('pere').checked,
                mere: document.getElementById('mere').checked,
                nb_grand_pere: document.getElementById('grand_pere').checked ? 1 : 0,
                nb_grand_mere_paternelle: document.getElementById('grand_mere_pat').checked ? 1 : 0,
                nb_grand_mere_maternelle: document.getElementById('grand_mere_mat').checked ? 1 : 0,
                fils: parseInt(document.getElementById('fils').value),
                filles: parseInt(document.getElementById('filles').value),
                nb_petits_fils: parseInt(document.getElementById('petits_fils').value),
                nb_petites_filles: parseInt(document.getElementById('petites_filles').value),
                freres: parseInt(document.getElementById('freres').value),
                soeurs: parseInt(document.getElementById('soeurs').value),
                freres_cons: parseInt(document.getElementById('freres_cons').value),
                soeurs_cons: parseInt(document.getElementById('soeurs_cons').value),
                freres_uter: parseInt(document.getElementById('freres_uter').value),
                soeurs_uter: parseInt(document.getElementById('soeurs_uter').value)
            };

            const response = await fetch('/api/calculer', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(data)
            });
            const res = await response.json();
            
            heritiersData = res.heritiers;
            let html = `<h3>Rapport de Répartition Successorale</h3>`;
            
            html += `<table class="no-print" style="margin-bottom:15px;">
                <tr><th>Total des Biens</th><th>Dettes Déduites</th><th>Testament (1/3 du reste)</th><th>Actif à Répartir</th></tr>
                <tr><td>${res.total_biens}</td><td>${res.dettes}</td><td>${res.testament}</td><td><strong>${res.actif_successoral}</strong></td></tr>
            </table>`;
            
            if (res.info_awl) {
                html += `<div class="awl-box no-print"><h4>⚠️ Application du Al-Awl (Réduction)</h4><p>${res.info_awl}</p></div>`;
            }
            
            if (res.info_radd) {
                html += `<div class="info-box no-print"><h4>ℹ️ Application du Al-Radd (Retour)</h4><p>${res.info_radd}</p></div>`;
            }
            
            if (res.exclusions && res.exclusions.length > 0) {
                html += '<div class="exclusions-box no-print"><h4>Exclusions appliquées (Al-Hajb)</h4><ul>';
                res.exclusions.forEach(exc => {
                    html += `<li>${exc}</li>`;
                });
                html += '</ul></div>';
            }
            
            html += '<table><tr><th>Héritier</th><th>Nb</th><th>Répartition de la Part</th><th>Part Finale (%)</th><th>Montant Total</th><th>Part Individuelle</th><th class="no-print">Explications</th></tr>';
            
            heritiersData.forEach((h, index) => {
                let actionsHtml = `
                    <button class="btn-action" style="background:#27ae60;" onclick="showModal('Détail - ${h.heritier}', heritiersData[${index}].detail)">Détail</button>
                    <button class="btn-action" style="background:#e67e22;" onclick="showModal('Source Coranique - ${h.heritier}', heritiersData[${index}].source)">Source</button>
                `;
                html += `<tr>
                    <td><strong>${h.heritier}</strong></td>
                    <td>${h.nombre}</td>
                    <td><small>${h.part_detail}</small></td>
                    <td>${h.part_pourcentage}</td>
                    <td>${h.montant_total}</td>
                    <td>${h.montant_individuel}</td>
                    <td class="no-print">${actionsHtml}</td>
                </tr>`;
            });
            html += '</table>';
            
            html += '<button class="btn-print no-print" onclick="window.print()">Sauvegarder en PDF / Imprimer</button>';
            
            const div = document.getElementById('resultats');
            div.innerHTML = html;
            div.style.display = 'block';
        }
    </script>
</body>
</html>
"""

@app.get("/")
async def get_index():
    return HTMLResponse(content=HTML_PAGE)

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)