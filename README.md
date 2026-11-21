<palign="center">
<imgsrc="docs/bilder/hero.png"alt="JarvisonNod:DeinpersönlicherKI-Helfer.ErwohntaufdeinemeigenenComputer."width="100%"/>
</p>

<palign="center">
<b>DieeinfachsteAnleitung,umdireineneigenenKI-HelferaufdeinenComputerzuholen.</b><br/>
OhneProgrammieren.OhneAbo.DeinGehirnbleibtzuHause.
</p>

<palign="center">
<ahref="#checkliste">✅Checkliste</a>·
<ahref="#ein-befehl">⚡Ein-Befehl-Weg</a>·
<ahref="#schritt-1">🪜SchrittfürSchritt</a>·
<ahref="#modelle">🧠WelchesModell?</a>·
<ahref="#profis">🧑‍💻FürProfis</a>·
<ahref="#hilfe">🆘Hilfe</a>
</p>

---

##👋Wasistdashier?

Stelldirvor,duhasteinenHelferwie**Jarvis**ausIronMan.Dusagstihm,wasdubrauchst,undererledigtes:imInternetsuchen,Texteschreiben,Termineprüfen,Dateienordnen.

DiesesRepo(„Repo“heißteinfach:einProjekt-OrdnerimInternet)isteine**Anleitung**.Siezeigtdir,wiedusoeinenHelferauf**deinemeigenenComputer**einrichtest.DafürnehmenwirzweikostenloseProgramme:

|Teil|Wasesist|Vergleich|
|---|---|---|
|🤲**[Nod](https://github.com/n8n-io/nod)**|EineAppvondenMachernvonn8n.SiehatWerkzeuge:Browser,Dateien,E-Mail,Kalender,Erinnerungen.|Die**Hände**|
|🧠**[Ollama](https://ollama.com)**(oder**[LMStudio](https://lmstudio.ai)**)|EinProgramm,daseinKI-ModellaufdeinemComputerlaufenlässt.|Das**Gehirn**|

Zusammensindsiedein**Jarvis**.🎉

<palign="center">
<imgsrc="docs/bilder/so-funktionierts.png"alt="SofunktioniertJarvis:Duschreibst,NodhatdieWerkzeuge,OllamaistdasGehirn.BeidesläuftaufdeinemComputer.InsInternetgehtesnurfürWebsuche."width="100%"/>
</p>

**Warumlokal?**
-🔒DeineFragenundGesprächegehennichtaneinefremdeKI-Firma.
-💶EskostetnichtsproFrage.KeinAbo.
-✈️DasGehirnfunktioniertauchohneInternet.(FürWebsuchebrauchstdunatürlichInternet.)

---

<aid="checkliste"></a>
##✅Checkliste:Wasbrauchstdu?

Hakeab,wasdu**schonhast**.DannspringstdudirektzumerstenPunkt,derfehlt.

||Was|Wofür|Soprüfstdues|Fehlt?Dann…|
|---|---|---|---|---|
|☐|**MacmitApple-Chip**(M1–M5)und**48GBRAM**odermehr<br><sub>Windows11gehtauch(Vorschau-Version)</sub>|DamitdasGehirnschnellgenugdenkt|Apfel-Menü→**ÜberdiesenMac**|[Schritt1](#schritt-1)|
|☐|**ca.40GBfreierSpeicherplatz**|FürModell(~24GB)undNod(~2GB)|Apfel-Menü→**Systemeinstellungen**→**Allgemein**→**Speicher**|Platzschaffen|
|☐|**Ollama**(oderLMStudio)|LässtdasGehirnlaufen|Lama-Symbol🦙obeninderMenüleiste|[Schritt2](#schritt-2)|
|☐|**EinModellmit„Tools“**,z.B.`qwen3.6:35b`|DasGehirnselbst|ImTerminal:`ollamalist`|[Schritt3](#schritt-3)|
|☐|**Kontextauf64k**(Ollama-Einstellung)|DamitNodgenug„Notizblock“hat|ImTerminal:`ollamaps`→Spalte**CONTEXT**|[Schritt4](#schritt-4)|
|☐|**Nod-App**|DieHändemitdenWerkzeugen|Ordner**Programme**→**Nod**|[Schritt5](#schritt-5)|
|☐|**NodmitOllamaverbunden**|DamitHändeundGehirnzusammenarbeiten|InNod:**Settings→Models**zeigt`localhost:11434`|[Schritt6](#schritt-6)|

>💡**DubrauchstKEINGitHub-Konto**,keinGit,keinDockerundkeinNode.js.DasallesbringtdieNod-Appselbstmit.

<palign="center">
<imgsrc="docs/bilder/wegweiser.png"alt="Wostehstdugerade?Neu:Schritt1.Ollamaschonda:Schritt3.Modellschonda:Schritt4.Profi:SchnellstartfürProfis."width="100%"/>
</p>

**Direktspringen:**[Ichbinganzneu→Schritt1](#schritt-1)·[Ollamaistschonda→Schritt3](#schritt-3)·[Modellistschonda→Schritt4](#schritt-4)·[IchbinProfi→Schnellstart](#profis)

---

<aid="ein-befehl"></a>
##⚡DerEin-Befehl-Weg(Mac)

DuwillstnichtallesvonHandmachen?Dannlassden**Helfer-Befehl**dieArbeiterledigen.ErprüftdeinenMac,suchtdaspassendeModellaus,lädtesherunter,stelltallesrichtigeinundtestetes.

1.Drücke<kbd>⌘Cmd</kbd>+<kbd>Leertaste</kbd>,tippe**Terminal**unddrücke<kbd>Enter</kbd>.
2.KopieredieseZeile,fügesieimTerminalein(<kbd>⌘Cmd</kbd>+<kbd>V</kbd>)unddrücke<kbd>Enter</kbd>:

```sh
curl-fsSLhttps://raw.githubusercontent.com/Paulito12209/jarvis-on-nod/main/scripts/jarvis-mac.sh|bash
```

3.Lies,wasaufdemBildschirmsteht.WenneineFragekommt,drücke<kbd>Enter</kbd>für„Ja“.
4.AmEndesteht,wasduinNodeintippenmusst.Dasist[Schritt6](#schritt-6).

<details>
<summary><b>WasmachtdieserBefehlgenau?(Istdassicher?)</b></summary>
<br/>

GuteFrage!MansolltenieblindBefehleausdemInternetausführen.DukannstdenganzenHelferhierlesen:[`scripts/jarvis-mac.sh`](scripts/jarvis-mac.sh).Er:

1.liest,wievielRAMdeinMachat,
2.wähltdaspassendeModell(48GB+→`qwen3.6:35b`,darunter→`gpt-oss:20b`),
3.hilftdir,Ollamazuinstallieren(überdieoffizielleWebseiteoderHomebrew),
4.stelltdenKontextauf64k(`OLLAMA_CONTEXT_LENGTH=65536`),
5.lädtdasModellundmachteinen**echtenWerkzeug-Test**,
6.fragtdich,oberdie**offizielle**Nod-Appinstallierensoll(mitdemInstallervonn8n).

ErlöschtnichtsundbrauchtkeinAdministrator-Passwort.

**Nurprüfen,ohneetwaszuändern:**
```sh
curl-fsSLhttps://raw.githubusercontent.com/Paulito12209/jarvis-on-nod/main/scripts/jarvis-mac.sh|bash-s----check
```

**LieberdasProgrammier-Modell?**
```sh
curl-fsSLhttps://raw.githubusercontent.com/Paulito12209/jarvis-on-nod/main/scripts/jarvis-mac.sh|bash-s----modelqwen3.6:27b
```

**Windows11?**Öffne**PowerShell**(nichtalsAdministrator)undfügeein:
```powershell
irmhttps://raw.githubusercontent.com/Paulito12209/jarvis-on-nod/main/scripts/jarvis-windows.ps1|iex
```
</details>

---

##🪜SchrittfürSchritt

Lieberallesselbstmachenundverstehen?Super!HieristdeinFahrplan.

<palign="center">
<imgsrc="docs/bilder/fahrplan.png"alt="Fahrplanin6Schritten:Computerprüfen,Ollamainstallieren,Modellladen,Notizblockvergrößern,Nodinstallieren,verbindenundloslegen.Zusammenetwa30bis45Minuten."width="100%"/>
</p>

<aid="schritt-1"></a>
###Schritt1·IstmeinComputerstarkgenug?⏱️2Min.

EinKI-Gehirnbrauchtviel**Arbeitsspeicher**(RAM).DasistderPlatz,andemderComputergeradedenkt.Jemehr,destogrößerundklügerdarfdasGehirnsein.

**Sofindestduesheraus(Mac):**
1.Klickeobenlinksaufdas**Apfel-Symbol**.
2.Klickeauf**ÜberdiesenMac**.
3.Schaubei**Chip**(sollte„AppleM…“sein)und**Speicher**(dasistderRAM).

<palign="center">
<imgsrc="docs/bilder/ram-ampel.png"alt="RAM-Ampel:64GBundmehrperfekt,48GBsehrgut,24bis32GBgehtmitkleineremModell,unter16GBzuwenig."width="100%"/>
</p>

>🧮**Beispiel:**EinMacminiM5Promit64GBistperfekt.ErkannbeideempfohlenenModellelaufenlassen.Mit48GBklapptesauchsehrgut.

<aid="schritt-2"></a>
###Schritt2·DasGehirn-Programminstallieren⏱️5Min.

DuhastzweiMöglichkeiten.**NimmWegA,wennduunsicherbist.**

<detailsopen>
<summary><b>WegA:Ollama(empfohlen)</b></summary>
<br/>

1.Öffne**[ollama.com/download](https://ollama.com/download)**.
2.Klickeauf**DownloadformacOS**.
3.ÖffnedieheruntergeladeneDateiundziehe**Ollama**indenOrdner**Programme**.
4.StarteOllama.ObenrechtsinderMenüleisteerscheinteinkleines**Lama**🦙.Dasheißt:Ollamaläuft.

**Test:**ÖffnedasTerminal(<kbd>⌘Cmd</kbd>+<kbd>Leertaste</kbd>→„Terminal“)undtippe:
```sh
ollama--version
```
SiehstdueineZahlwie`ollamaversionis0.x.x`?Perfekt!✅
</details>

<details>
<summary><b>WegB:LMStudio(mitschönerOberfläche)</b></summary>
<br/>

1.Öffne**[lmstudio.ai](https://lmstudio.ai)**undladedieMac-Version.
2.InstallieresiewiejedeandereAppundöffnesie.
3.DasModelllädstduin[Schritt3](#schritt-3)direktinLMStudioüberdie**Suche**(Lupe).

**WichtigbeiLMStudio:**DieAdressefürNodistspäter`http://localhost:1234/v1`(nicht11434).
</details>

<details>
<summary><b>💡Wasisteigentlichdas„Terminal“?</b></summary>
<br/>

DasTerminalisteinFenster,indasmanBefehletippt,stattzuklicken.KeineAngst:Dukannstdamitnichtskaputtmachen,solangedunurdieBefehleausdieserAnleitungbenutzt.

-**Öffnen:**<kbd>⌘Cmd</kbd>+<kbd>Leertaste</kbd>,„Terminal“tippen,<kbd>Enter</kbd>.
-**Befehleinfügen:**<kbd>⌘Cmd</kbd>+<kbd>V</kbd>,dann<kbd>Enter</kbd>.
-**Etwasabbrechen:**<kbd>Ctrl</kbd>+<kbd>C</kbd>.
</details>

<aid="schritt-3"></a>
###Schritt3·DasGehirn(Modell)herunterladen⏱️10–20Min.

Ein**Modell**istdaseigentlicheGehirn.EsisteinesehrgroßeDatei(ca.17–24GB).Wirempfehlengenau**zwei**Modelle.MehrdazuimAbschnitt[WelchesModell?](#modelle).

**MitOllama:**TippeimTerminal:

```sh
ollamapullqwen3.6:35b
```

JetztläufteinBalken.DasdauerteineWeile.ZeitfüreinenKakao!☕

>DuwillstspäterauchdasProgrammier-Modell?Dannzusätzlich:`ollamapullqwen3.6:27b`

**MitLMStudio:**Klickeaufdie**Lupe**🔍,suchenach**qwen3.6**,wähle**Qwen3.635BA3B**(aufdemMacdie**MLX**-Version)undklicke**Download**.

**Test(Ollama):**
```sh
ollamalist
```
Steht`qwen3.6:35b`inderListe?✅

<aid="schritt-4"></a>
###Schritt4·DenNotizblockvergrößern⏱️1Min.

**DieserSchrittistsuperwichtig!**Diemeistenvergessenihn,unddannwirktJarvis„dumm“.

DasGehirnhateinen**Notizblock**(aufEnglisch:*Contextlength*).Daraufschreibtesalles,wasessichgerademerkenmuss.NodgibtdemGehirneinelangeAnleitungmitallenWerkzeugen.Diealleinbrauchtschonca.20.000„Wörter“(Tokens).VieleProgrammestartenabermitnur4.000.DannpasstNodsAnleitunggarnichtdrauf!

<palign="center">
<imgsrc="docs/bilder/kontext.png"alt="DerNotizblock:4kistzuklein,32kgehtknapp,64kbrauchstdu.Sostellstduesein:Ollama-Symbol,Settings,Contextlength,Reglerauf64k."width="100%"/>
</p>

**MitOllama:**
1.KlickeobeninderMenüleisteaufdas**Lama**🦙.
2.Klickeauf**Settings**.
3.Schiebe**Contextlength**auf**64k**(odermehr).
4.BeendeOllamaeinmalundstarteesneu.

**MitLMStudio:**WenndudasModelllädst,stelle**ContextLength**auf**65536**(odermehr).

**Test(Ollama):**StelledemModelleinekurzeFrage,damiteslädt,undschaudannnach:
```sh
ollamarunqwen3.6:35b"SagHallo"
ollamaps
```
InderSpalte**CONTEXT**sollte**65536**stehen.✅

<aid="schritt-5"></a>
###Schritt5·Nodinstallieren⏱️5–10Min.

1.LadeNodfürdeinenMac:**[NodfürApple-Chip(M1–M5)](https://github.com/n8n-io/nod/releases/latest/download/nod-arm64.dmg)**
<sub>(ÄltererMacmitIntel?[Hier](https://github.com/n8n-io/nod/releases/latest/download/nod-x64.dmg).Windows11?[Hier](https://github.com/n8n-io/nod/releases/latest/download/nod-Setup-x64.exe).)</sub>
2.ÖffnedieDateiundziehe**Nod**indenOrdner**Programme**.
3.ÖffneNod.DerMacfragt:„Möchtestdudasöffnen?“→**Öffnen**.
4.Klickeauf**Getstarted**.
5.Nodlädtjetzteinmalseineneigenenkleinen„ComputerimComputer“herunter(ca.1,8GB).LassdasInternetanundwarte,bisesfertigist.

>🔐FragtderMacnachdeinem**Schlüsselbund-Passwort**?Dasistnormal.NodspeichertdamitdeinePasswörtersicher.

<aid="schritt-6"></a>
###Schritt6·HändeundGehirnverbinden⏱️2Min.

JetztsagstduNod,wodasGehirnwohnt.

1.WennNodnacheinemModellfragt:Klickeauf**Moreproviders**unddannauf**Yourownserver**.
<sub>(Späterfindestdudasunter**Settings→Models→Add→OpenAI-compatible**.)</sub>
2.Bei**Serveraddress**stehtschon`http://localhost:11434/v1`.DasistOllama.✅
<sub>(BeiLMStudioänderstdueszu`http://localhost:1234/v1`.)</sub>
3.**APIkey**:leerlassen.
4.Klickeauf**Connect**.

<palign="center">
<imgsrc="docs/bilder/nod-eigener-server.png"alt="EchterScreenshotausNod:Seite'Yourownserver'mitderServer-Adressehttp://localhost:11434/v1,einemleerenFeldfürdenAPI-KeyunddemKnopfConnect."width="80%"/>
<br/><sub>EchterScreenshotausNod(©n8nGmbH,Apache2.0)</sub>
</p>

5.WähledeinModellaus:**qwen3.6:35b**.

Wennallesklappt,siehstduunter**Settings→Models**soetwas:

<palign="center">
<imgsrc="docs/bilder/nod-verbunden.png"alt="EchterScreenshotausNod:UnterOpenAI-compatiblestehtlocalhost:11434mitdemHinweisSelected."width="80%"/>
<br/><sub>EchterScreenshotausNod(©n8nGmbH,Apache2.0)</sub>
</p>

🎉**Geschafft!DeinJarvislebt.**

---

<aid="erste-aufgaben"></a>
##🚀Probieresaus:DeineerstenAufgaben

SchreibJarviseinfach,wasduwillst.Ganznormal,wieeinerPerson.HiereinpaarIdeen:

|Wasduschreibst|WasJarvisdafürbenutzt|
|---|---|
|„WassindheutediewichtigstenNachrichtenzuKI?Fassesiein5Punktenzusammen.“|🔎Websuche,🌐Webseitenlesen|
|„VergleichediedreibestenKaffeemaschinenunter300€undmacheineTabelle.“|🔎Websuche,✍️Schreiben|
|„SchreibeinefreundlicheE-MailanmeinenVermieterwegenderkaputtenHeizung.“|✍️Schreiben|
|„ErinneremichjedenMontagum9UhranmeineWochenplanung.“|⏰Zeitpläne|
|„BaumireinekleineWebseitefürmeinenHundesitter-Service.“|💻Code(nimmdafürModell2)|

>🐢**DieersteAntwortdauertlänger.**DasGehirnmusserst„aufwachen“undNodslangeAnleitunglesen.Danachgehtesschneller.

---

<aid="modelle"></a>
##🧠WelchesModellsollichnehmen?

EsgibttausendeModelle.Wirmachenesdirleicht:**Nimmeinsvondiesenzwei.**Beidesindkostenlos,beidekönnenWerkzeugebenutzen,beidelaufengutaufeinemMacmit48–64GB.

<palign="center">
<imgsrc="docs/bilder/modelle.png"alt="ZweiModelle:Modell1qwen3.6:35b,derschnelleAllrounderfürRecherche,WebsucheundSchreiben.Modell2qwen3.6:27b,dergründlicheBauerfürProgrammierenundApps."width="100%"/>
</p>

###⚡Modell1:DerschnelleAllrounder·`qwen3.6:35b`

**NimmdiesesModellzuerst.**

-**Warumschnell?**Esisteinsogenanntes**MoE-Modell**(„MixtureofExperts“).StelldireineFirmamit35MilliardenMitarbeiternvor.BeijederFragearbeitenabernurdie3Milliarden,diesichdamitambestenauskennen.Darumantwortetesflott.
-**Superfür:**Fragenbeantworten,imInternetrecherchieren,TexteundE-Mailsschreiben,Zusammenfassungen,Alltags-Aufgaben.
-**Download:**ca.24GB·**RAM:**ab48GBempfohlen
-**Laden:**`ollamapullqwen3.6:35b`

###🛠️Modell2:DergründlicheBauer·`qwen3.6:27b`

**HoldirdiesesModell,wennduetwasbauenwillst.**

-**Warumgründlich?**Esistein**Dense-Modell**.HierarbeitenbeijederFragealle27Milliarden„Mitarbeiter“mit.Dasistlangsamer,abersehrsorgfältig.BeimProgrammierengehörteszudenstärkstenModellen,dieaufeinenHeim-Computerpassen.
-**Superfür:**AppsundWebseitenbauen,Codeverstehenundreparieren,langeAufgabenmitvielenSchritten.
-**Download:**ca.17GB·**RAM:**ab32GB,besser48GB
-**Laden:**`ollamapullqwen3.6:27b`

>🔁**Wechseln:**InNodunter**Settings→Models**kannstdujederzeitdasandereModellauswählen.Mit64GBkannstdubeideinstallierthaben.Mit48GBnimmambestenimmernureinszurZeit.

<details>
<summary><b>WarumkeineanderenModelle?</b></summary>
<br/>

-**GrößereModelle**(z.B.65Milliarden„Teile“undmehr)passenkaumauf64GB,weilNodunddeinMacauchnochPlatzbrauchen.
-**KleinereModelle**sindschneller,machenabermehrFehler.DasistbeiNodwichtig:DasModellentscheidetauchmit,**wannNoddichvorherfragenmuss**.KleineModelleliegendaöfterfalsch.
-**Wichtigist„Tools“:**EinModellohneWerkzeug-FähigkeitkanninNodnurplaudern.Auf[ollama.com](https://ollama.com/search?c=tools)erkennstduguteModelleamEtikett**tools**.
-DieModell-Weltändertsichschnell.DieseEmpfehlungistvom**November2026**.
</details>

###🔎WarumistWebsuchesowichtig?

EinModellhatirgendwannaufgehörtzulernen.Alles,wasdanachpassiertist,**weißesnicht**.EsistwieeinsehrklugerFreund,dereinJahraufeinereinsamenInselwar.

Mit**Websuche**kannJarvisnachschauen:
-📰**NeueFakten:**Nachrichten,Preise,Wetter,Öffnungszeiten.
-📚**Recherche:**MehrereQuellenlesen,vergleichenundzusammenfassen.
-✅**WenigerErfinden:**Stattzuraten,liestJarvisnachundnenntdieQuelle.

NodhatWebsucheschoneingebaut.Dumusstnichtsextraeinrichten.

###🧰Wasist„ToolCalling“?

**ToolCalling**heißt:DasGehirnkann**Werkzeugebenutzen**.EskannselbstnichtklickenoderinsInternetgehen.AbereskannNodsagen:„BittebenutzejetztdieWebsuchemitdiesenWörtern.“NodmachtdasundgibtdasErgebniszurück.

<palign="center">
<imgsrc="docs/bilder/tool-calling.png"alt="ToolCallingin4Schritten:DufragstnachdemWetter.DasGehirnmerkt,dassesdieWebsuchebraucht.NodsuchtimInternet.JarvisantwortetmitdemErgebnis."width="100%"/>
</p>

DafüristToolCallinggut:
-🔎**Recherche:**suchen,Webseitenlesen,Faktenprüfen.
-💻**Programmieren:**Codeschreiben,ausführen,Fehlerfinden,Dateienspeichern.
-📧**Erledigungen:**E-Mailsentwerfen,Termineeintragen,Erinnerungensetzen.

**KeineSorge:**BevorNodetwasWichtigesfürdichtut(z.B.eineE-Mailabschicken),**fragtesdichvorher**.Darumheißtes„Nod“,wieeinNicken:EswartetaufdeinOkay.

---

<aid="hilfe"></a>
##🆘Hilfe!Etwasklapptnicht

|Problem|Lösung|
|---|---|
|Nodsagt**„ThisserverhasnomodelsNodcanuse“**|DeinModellkannkeineWerkzeuge.Ladeeinsder[zweiempfohlenenModelle](#modelle).|
|Nodsagt**„Modeldiscoveryfailed“**|LäuftOllama?SchaunachdemLama🦙obeninderMenüleiste.TestimTerminal:`curlhttp://localhost:11434/v1/models`|
|Jarvis**vergisstseineWerkzeuge**,wiederholtsichoderignoriertdich|DerNotizblockistzuklein.Mach[Schritt4](#schritt-4)nochmalundstarteOllamaneu.|
|Die**ersteAntwortdauertewig**|Dasistnormal(biszu1–2Minuten).NacheinerMinutezeigtNod„Waitingfor…“.Einfachwarten.|
|DerMacwird**sehrlangsam**|ZuwenigRAMfrei.SchließegroßeProgramme(z.B.Spiele,vieleBrowser-Tabs)odernimmModell2(kleiner).|
|Ein**neuesModell**erscheintnichtinNod|Settings→Models→**Manage**neben„OpenAI-compatible“→dieselbeAdressenochmalhinzufügen.DaslädtdieListeneu.|
|Nod**fragtvorfastallem**nach|KleineModellesindbeidieserEntscheidungunsicher.Nimm`qwen3.6:35b`oder`qwen3.6:27b`.|
|**Ichweißnicht,wasfehlt**|LassdenPrüf-Befehllaufen.Erändertnichtsundzeigtdirrot,wasfehlt:<br/>`curl-fsSLhttps://raw.githubusercontent.com/Paulito12209/jarvis-on-nod/main/scripts/jarvis-mac.sh\|bash-s----check`|

NochmehrHilfe:[Nod-DokuzulokalenModellen(Englisch)](https://nod.n8n.io/docs/connect/local-models/)·[NodDiscord](https://discord.gg/n8n)

---

<aid="profis"></a>
##🧑‍💻SchnellstartfürProfis

DukennstTerminal,Homebrewund`.env`-Dateien?HieristallesinKurzform.

```sh
#1)Ollama+Modell
brewinstall--caskollama
launchctlsetenvOLLAMA_CONTEXT_LENGTH65536#oderinderOllama-App:Settings→Contextlength
open-aOllama
ollamapullqwen3.6:35b#Allrounder(MoE,3Baktiv,~24GB)
ollamapullqwen3.6:27b#Coding(dense,~17GB),optional

#Prüfen:Tool-Fähigkeit+geladenerKontext
curl-slocalhost:11434/api/show-d'{"model":"qwen3.6:35b"}'|grep-o'"capabilities":[^]]*]'
ollamarunqwen3.6:35b"hi">/dev/null&&ollamaps

#2)NodDesktop(offiziellerInstallervonn8n)
curl-fsSLhttps://raw.githubusercontent.com/n8n-io/nod/main/deployment/n8n/install.sh|sh

#3)InNod:Moreproviders→Yourownserver→http://localhost:11434/v1
```

**NodausdemQuellcode**(brauchtNode.js24.21+,pnpm,Docker):

```sh
gitclonehttps://github.com/n8n-io/nod.git&&cdnod
corepackenable
pnpmstart#erzeugt.envaus.env.example
```

Dannin`nod/.env`:

```sh
LLM_PROVIDER=compatible
OPENAI_COMPATIBLE_BASE_URL=http://localhost:11434/v1#LMStudio:http://localhost:1234/v1
OPENAI_COMPATIBLE_API_KEY=
LLM_MODEL=qwen3.6:35b
#NOD_TRUST_MODEL=selected#Standard:deinModellprüftAktionenselbst(niedrigsteReasoning-Stufe)
```

**Gutzuwissen:**
-Nodbraucht**ToolCalling**und**≥64kKontext**(System-Prompt+Tools≈20kTokens).
-Miteinem`localhost`-ModellkostetChatnichts.Der**Trust-Check**nutztstandardmäßigdeingewähltesModell.Mit`NOD_TRUST_MODEL=llm`oder`decision`kanneinexternerkleinerCheckergenutztwerden(kannAPI-Kostenhaben).Details:[Decisionchecks](https://nod.n8n.io/docs/connect/models/#decision-checks).
-WebsucheläuftüberNodseingebautesWeb-Plugin(Standard:Exa,ohneAPI-KeyüberExasöffentlichenDienst).DieSuchanfrageselbstgehtalsoinsInternet.
-vLLM:`--enable-auto-tool-choice--tool-call-parser<parser>--max-model-len65536`;llama.cpp:`llama-server-c65536--jinja`.

---

##🔒Wasbleibtprivat?

-**DeineGesprächemitdemGehirn**bleibenaufdeinemComputer(beiOllama/LMStudio).
-**Websuche**schicktdieSuchwörteraneinenSuchdienst.Webseiten,dieJarvisliest,sehendenBesuch.
-**VerbundeneApps**(Gmail,Kalender…)laufenübereinenVerbindungsdienstvonn8n.
-**Nutzungsdaten:**NodschicktstandardmäßigeinfacheNutzungsdatenann8n.Ausschalten:**Settings→Privacy&data→Shareusagedata**.

Genaunachlesen:[Nod:Yourdataandprivacy](https://nod.n8n.io/docs/trust/privacy/)

---

##💻KeinstarkerComputer?

-**24–32GBRAM:**Nimm`gpt-oss:20b`(`ollamapullgpt-oss:20b`).Dasklappt,machtabermehrFehler.
-**WenigerRAM:**EinlokalesGehirnwirdzulangsam.Nodkannstattdessenein**Online-Modell**nutzen(z.B.miteinemChatGPT-AboodereinemAPI-Schlüssel).DaskostetGeldundistnichtmehrganzprivat.Anleitung:[Nod:Models](https://nod.n8n.io/docs/connect/models/).

---

##📖KleinesWörterbuch

|Wort|Einfacherklärt|
|---|---|
|**KI-Modell/LLM**|Das„Gehirn“.EinegroßeDatei,diegelernthat,Sprachezuverstehenundzuschreiben.|
|**Lokal**|AufdeinemeigenenComputer,nichtimInternet.|
|**RAM/Arbeitsspeicher**|DerPlatz,andemderComputergeradedenkt.Jemehr,destogrößerdarfdasGehirnsein.|
|**Ollama/LMStudio**|Programme,dieeinGehirnaufdeinemComputerlaufenlassen.|
|**Nod**|DieAppmitdenWerkzeugen.SiefragtdasGehirn,waszutunist,undtutesdann.|
|**ToolCalling**|DasGehirnkannWerkzeugebenutzen(suchen,Dateienöffnen,Codeausführen…).|
|**Kontext/Contextlength**|DerNotizblockdesGehirns.SovielTextkannessichaufeinmalmerken.|
|**Token**|EinStückchenText,ungefähreinWortteil.1.000Tokens≈750Wörter.|
|**MoE(MixtureofExperts)**|EinGehirn,beidemproFragenurdiepassenden„Experten“arbeiten.Schnell!|
|**Dense**|EinGehirn,beidemimmeralleTeilemitarbeiten.Gründlich,aberlangsamer.|
|**Terminal**|EinFenster,indasmanBefehletipptstattzuklicken.|
|**localhost**|„DieserComputerhier.“`localhost:11434`heißt:OllamaaufdeinemComputer.|
|**Repo**|EinProjekt-OrdneraufGitHub.Wiedieserhier.|

---

##🤔WarumNodundnichtOpenJarvis?

[OpenJarvis](https://github.com/open-jarvis/OpenJarvis)(Stanford)istaucheintoller,lokalerJarvis.ErläuftebenfallsmitOllama,LMStudio,MLXundanderenlokalenGehirnen.EristabereherfürEntwicklerundForschergedacht(Python,Kommandozeile,vieleEinstellungen).

**Nod**hateinefertigeAppmitKnöpfen,fragtvorwichtigenAktionennachundlässtsichohneProgrammiereneinrichten.DarumnutzenwirhierNod.

---

##📁WasistindiesemRepo?

```
jarvis-on-nod/
├──README.md←dieseAnleitung
├──scripts/
│├──jarvis-mac.sh←Helfer-BefehlfürdenMac(einrichten+prüfen)
│└──jarvis-windows.ps1←Helfer-BefehlfürWindows11
├──docs/
│├──bilder/←alleBilderdieserAnleitung
│└──quellen/←QuelldateienderBilder(HTML),zumÄndern
└──NOTICE←HinweisezufremdenInhalten(Nod-Screenshots)
```

<details>
<summary>Bilderneuerzeugen(fürMitmacher)</summary>
<br/>

DieGrafikenentstehenaus[`docs/quellen/bilder.html`](docs/quellen/bilder.html).ÄnderedenTextdortunderzeugedieBilderneu(brauchtNode.jsundPlaywright):

```sh
nodedocs/quellen/render.jsdocs/bilder
```
</details>

---

<palign="center">
<sub>
NodisteinProjektvon<ahref="https://n8n.io">n8n</a>(<ahref="https://github.com/n8n-io/nod">github.com/n8n-io/nod</a>,Apache2.0).<br/>
DieseAnleitungisteinunabhängigesCommunity-Projektundnichtvonn8n.<br/>
StandderAnleitung:November2026.
</sub>
</p>
