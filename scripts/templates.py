"""Hand-written text templates for the synthetic datasets: (event_type, sentiment, style, template).

Placeholders: {co} company name, {co2} second company, {tk} ticker, {pct} percent, {bp} basis points,
{amt} money amount, {q} quarter, {region} generic region, {product} product name.
All companies and events are fictional. Templates are grouped (template_id) so that model evaluation
can hold out entire templates and avoid measuring memorisation.
"""

T = [
    # ---------------- Geopolitical ----------------
    ("Geopolitical", "Negative", "news", "Sanctions widen after military clashes near {region}; analysts warn {co} faces export restrictions"),
    ("Geopolitical", "Negative", "news", "Escalating border conflict in {region} rattles global markets as investors flee risk assets"),
    ("Geopolitical", "Negative", "news", "Naval blockade of {region} threatens shipping routes used by {co}"),
    ("Geopolitical", "Negative", "news", "Government imposes export controls on advanced chips amid rising geopolitical tension, hitting {co}"),
    ("Geopolitical", "Negative", "news", "Missile strikes near {region} push oil higher and send equities lower across the region"),
    ("Geopolitical", "Negative", "news", "Trade war fears return as new tariffs announced on imports, {co} flags supply risk"),
    ("Geopolitical", "Positive", "news", "Ceasefire agreed in {region}; diplomatic talks ease pressure on shipping and energy markets"),
    ("Geopolitical", "Neutral", "news", "Diplomats meet to discuss the {region} dispute; no change to existing sanctions expected this week"),
    ("Geopolitical", "Negative", "news", "Embargo on a major oil exporter tightens supply as conflict spreads in {region}"),
    ("Geopolitical", "Negative", "news", "Coup attempt in a neighbouring state disrupts {co} operations and raises regional political risk"),
    ("Geopolitical", "Negative", "social", "Sanctions just got way worse. ${tk} has big exposure to {region}, this is ugly"),
    ("Geopolitical", "Negative", "social", "War headlines again. Risk-off everywhere, oil spiking, ${tk} getting crushed"),
    ("Geopolitical", "Positive", "social", "Ceasefire in {region} confirmed!! relief rally incoming, shipping names like ${tk} bouncing"),
    ("Geopolitical", "Negative", "social", "Reportedly new export ban coming on chips, ${tk} could be hit hard if true"),
    ("Geopolitical", "Neutral", "social", "Watching the {region} talks today. Nothing priced in yet either way"),
    ("Geopolitical", "Negative", "social", "Military escalation near {region} is not good for anyone holding ${tk}"),

    # ---------------- Macroeconomic ----------------
    ("Macroeconomic", "Negative", "news", "Central bank delivers surprise {bp} basis point rate hike as inflation stays stubbornly high"),
    ("Macroeconomic", "Negative", "news", "Inflation accelerates to {pct}% annual pace, raising odds of further monetary tightening"),
    ("Macroeconomic", "Negative", "news", "GDP contracts for a second quarter, confirming a technical recession in the economy"),
    ("Macroeconomic", "Positive", "news", "Jobs report beats forecasts as unemployment falls to a multi-year low"),
    ("Macroeconomic", "Positive", "news", "Central bank signals rate cut as inflation cools faster than expected"),
    ("Macroeconomic", "Negative", "news", "Manufacturing PMI slumps to its weakest level in three years as orders dry up"),
    ("Macroeconomic", "Neutral", "news", "Central bank holds interest rates steady, in line with economists' expectations"),
    ("Macroeconomic", "Negative", "news", "Consumer confidence drops sharply as rising prices squeeze household spending"),
    ("Macroeconomic", "Negative", "news", "Government bond yield curve inverts further, a classic signal of recession risk for the economy"),
    ("Macroeconomic", "Positive", "news", "Economic growth surprises to the upside at {pct}% annualised, lifting the outlook for {co}"),
    ("Macroeconomic", "Negative", "social", "CPI hot again. {bp}bp hike basically locked in. rates going higher for longer"),
    ("Macroeconomic", "Negative", "social", "Recession is here, GDP negative two quarters in a row. Banks like ${tk} will feel it"),
    ("Macroeconomic", "Positive", "social", "Rate cut talk from the central bank!! growth stocks love this, ${tk} up"),
    ("Macroeconomic", "Neutral", "social", "Rates unchanged as expected. Market shrugging it off"),
    ("Macroeconomic", "Negative", "social", "Inflation print ugly. Real estate names like ${tk} sliding on higher rates"),
    ("Macroeconomic", "Negative", "social", "Unemployment ticking up and consumer spending weak, economy losing steam fast"),

    # ---------------- Credit Event ----------------
    ("Credit Event", "Negative", "news", "{co} downgraded to junk by rating agency after leverage surges"),
    ("Credit Event", "Negative", "news", "{co} missed a coupon payment on its senior bonds, triggering a grace period"),
    ("Credit Event", "Negative", "news", "{co} files for Chapter 11 bankruptcy protection after talks with creditors fail"),
    ("Credit Event", "Negative", "news", "Rating agency places {co} on negative watch citing covenant breach risk"),
    ("Credit Event", "Negative", "news", "{co} enters debt restructuring talks as its bonds trade at distressed levels"),
    ("Credit Event", "Negative", "news", "{co} defaults on a {amt} term loan, lenders form an ad hoc creditors committee"),
    ("Credit Event", "Positive", "news", "{co} credit rating upgraded to investment grade on improved cash flow"),
    ("Credit Event", "Negative", "news", "Non-performing loans tied to {co} rise as delinquencies climb"),
    ("Credit Event", "Neutral", "news", "Rating agency affirms {co} credit rating with a stable outlook"),
    ("Credit Event", "Negative", "news", "{co} warns it may be unable to meet debt obligations due next quarter"),
    ("Credit Event", "Negative", "social", "${tk} just got downgraded to junk. bonds tanking, default risk real"),
    ("Credit Event", "Negative", "social", "Heard ${tk} missed an interest payment?? creditors are going to be furious"),
    ("Credit Event", "Negative", "social", "${tk} bankruptcy filing confirmed. equity is basically zero now"),
    ("Credit Event", "Positive", "social", "${tk} upgraded by the rating agency, credit spreads tightening nicely"),
    ("Credit Event", "Negative", "social", "Rumour that ${tk} is hiring restructuring advisers. distressed debt desks circling"),
    ("Credit Event", "Neutral", "social", "${tk} rating affirmed, outlook stable. nothing to see here"),

    # ---------------- Merger & Acquisition ----------------
    ("Merger & Acquisition", "Positive", "news", "{co} agrees to acquire {co2} in a {amt} all-cash deal, citing cost synergies"),
    ("Merger & Acquisition", "Neutral", "news", "{co} confirms early-stage merger talks with {co2}; no agreement has been reached"),
    ("Merger & Acquisition", "Positive", "news", "{co2} shareholders approve takeover by {co} at a {pct}% premium"),
    ("Merger & Acquisition", "Negative", "news", "{co} takeover bid for {co2} collapses after financing falls through"),
    ("Merger & Acquisition", "Neutral", "news", "{co} to divest its logistics unit in a spin-off expected to close next year"),
    ("Merger & Acquisition", "Positive", "news", "Private equity firm launches {amt} leveraged buyout of {co}"),
    ("Merger & Acquisition", "Neutral", "news", "{co} acquires a minority stake in a regional start-up for an undisclosed sum"),
    ("Merger & Acquisition", "Negative", "news", "Acquisition of {co2} will add {amt} of debt to {co}'s balance sheet, analysts caution"),
    ("Merger & Acquisition", "Positive", "news", "{co} and {co2} announce merger of equals to create a sector leader"),
    ("Merger & Acquisition", "Positive", "social", "${tk} buying {co2}!! huge deal, synergies look great"),
    ("Merger & Acquisition", "Neutral", "social", "Merger talks between ${tk} and {co2} reportedly ongoing. could go either way"),
    ("Merger & Acquisition", "Negative", "social", "${tk} overpaying for {co2} with borrowed money. acquisition looks like a mistake"),
    ("Merger & Acquisition", "Positive", "social", "Takeover premium of {pct}% for ${tk} holders, nice payday"),
    ("Merger & Acquisition", "Neutral", "social", "${tk} tender offer details out today, reading the filing now"),

    # ---------------- Product Launch ----------------
    ("Product Launch", "Positive", "news", "{co} unveils its next-generation {product}, promising faster performance at lower cost"),
    ("Product Launch", "Positive", "news", "{co} launches new {product} in three markets ahead of schedule"),
    ("Product Launch", "Neutral", "news", "{co} introduces an updated {product}; pricing will be announced later"),
    ("Product Launch", "Negative", "news", "{co} delays launch of its new {product} after testing problems"),
    ("Product Launch", "Positive", "news", "Pre-orders for {co}'s new {product} exceed expectations in the first week"),
    ("Product Launch", "Positive", "news", "{co} rolls out {product} to enterprise clients after a successful pilot"),
    ("Product Launch", "Neutral", "news", "{co} to debut its {product} at an industry conference next month"),
    ("Product Launch", "Negative", "news", "Reviews of {co}'s newly launched {product} are lukewarm as rivals cut prices"),
    ("Product Launch", "Positive", "social", "${tk} new {product} launch looks amazing, demand is going to be huge"),
    ("Product Launch", "Negative", "social", "${tk} launch event was a flop. {product} is late and overpriced"),
    ("Product Launch", "Neutral", "social", "${tk} unveiling the {product} tomorrow. curious to see specs"),
    ("Product Launch", "Positive", "social", "Just tried the new ${tk} {product}. honestly impressive"),

    # ---------------- Earnings / Financial Results ----------------
    ("Earnings / Financial Results", "Positive", "news", "{co} {q} earnings beat estimates as revenue climbs {pct}%"),
    ("Earnings / Financial Results", "Negative", "news", "{co} misses {q} profit expectations and cuts full-year guidance"),
    ("Earnings / Financial Results", "Positive", "news", "{co} raises outlook after record quarterly revenue and wider margins"),
    ("Earnings / Financial Results", "Negative", "news", "{co} reports a {q} net loss as costs surge and margins shrink"),
    ("Earnings / Financial Results", "Neutral", "news", "{co} {q} results in line with consensus; guidance maintained"),
    ("Earnings / Financial Results", "Positive", "news", "{co} lifts dividend and announces {amt} buyback after strong annual results"),
    ("Earnings / Financial Results", "Negative", "news", "{co} warns of weaker {q} revenue as demand softens"),
    ("Earnings / Financial Results", "Negative", "news", "{co} EPS falls {pct}% year on year, below analyst estimates"),
    ("Earnings / Financial Results", "Positive", "news", "{co} beats {q} EPS estimates but warns on next quarter's margins"),
    ("Earnings / Financial Results", "Positive", "social", "${tk} crushed earnings!! revenue up {pct}%, guidance raised"),
    ("Earnings / Financial Results", "Negative", "social", "${tk} earnings miss and guidance cut. ouch"),
    ("Earnings / Financial Results", "Neutral", "social", "${tk} {q} numbers basically in line. stock flat after hours"),
    ("Earnings / Financial Results", "Negative", "social", "${tk} profit warning out. margins getting squeezed hard"),
    ("Earnings / Financial Results", "Positive", "social", "Strong quarter from ${tk}, net income way ahead of consensus"),

    # ---------------- Regulatory / Legal ----------------
    ("Regulatory / Legal", "Negative", "news", "Regulator fines {co} {amt} over misleading disclosures"),
    ("Regulatory / Legal", "Negative", "news", "{co} sued in class action lawsuit alleging securities fraud"),
    ("Regulatory / Legal", "Negative", "news", "Antitrust regulator opens investigation into {co}'s pricing practices"),
    ("Regulatory / Legal", "Positive", "news", "Court rules in favour of {co} in long-running patent litigation"),
    ("Regulatory / Legal", "Neutral", "news", "{co} reaches settlement with regulator; no admission of wrongdoing"),
    ("Regulatory / Legal", "Negative", "news", "Watchdog suspends {co}'s operating licence pending a compliance review"),
    ("Regulatory / Legal", "Negative", "news", "New capital rules from the banking regulator could force {co} to raise equity"),
    ("Regulatory / Legal", "Positive", "news", "Regulator grants {co} approval for its new {product}"),
    ("Regulatory / Legal", "Negative", "news", "Prosecutors widen probe into {co} executives over alleged bribery"),
    ("Regulatory / Legal", "Negative", "social", "${tk} hit with a {amt} fine by the regulator. compliance team asleep?"),
    ("Regulatory / Legal", "Negative", "social", "Class action against ${tk} filed today. lawyers everywhere"),
    ("Regulatory / Legal", "Positive", "social", "${tk} wins in court!! patent ruling a big relief"),
    ("Regulatory / Legal", "Neutral", "social", "${tk} settlement with the regulator announced. amount not disclosed"),
    ("Regulatory / Legal", "Negative", "social", "Antitrust probe into ${tk} could drag on for years"),

    # ---------------- Cybersecurity ----------------
    ("Cybersecurity", "Negative", "news", "Ransomware attack forces {co} to shut down core systems; customer data may be exposed"),
    ("Cybersecurity", "Negative", "news", "{co} discloses data breach affecting millions of customer records"),
    ("Cybersecurity", "Negative", "news", "Hackers gained unauthorized access to {co}'s payment network for several weeks"),
    ("Cybersecurity", "Negative", "news", "DDoS attack knocks {co}'s online banking platform offline"),
    ("Cybersecurity", "Neutral", "news", "{co} patches critical software vulnerability; no evidence of exploitation found"),
    ("Cybersecurity", "Negative", "news", "Phishing campaign targeting {co} employees leads to leaked data, regulators notified"),
    ("Cybersecurity", "Positive", "news", "{co} restores systems after cyber incident; says no customer funds were lost"),
    ("Cybersecurity", "Negative", "news", "Malware found in {co}'s supplier software raises supply chain cyber risk"),
    ("Cybersecurity", "Negative", "news", "{co} confirms cyberattack disrupted trading systems across the sector"),
    ("Cybersecurity", "Negative", "social", "${tk} got hacked?? app down and people seeing weird transactions"),
    ("Cybersecurity", "Negative", "social", "Massive data breach at ${tk}. change your passwords now"),
    ("Cybersecurity", "Negative", "social", "Ransomware gang claims they hit ${tk}. leaked records posted online"),
    ("Cybersecurity", "Neutral", "social", "${tk} says the vulnerability is patched. waiting for the full report"),
    ("Cybersecurity", "Positive", "social", "${tk} systems back online after the cyber incident, no funds lost"),

    # ---------------- Operational Disruption ----------------
    ("Operational Disruption", "Negative", "news", "Fire at {co}'s main plant halts production for at least two weeks"),
    ("Operational Disruption", "Negative", "news", "Workers at {co} begin indefinite strike, disrupting deliveries"),
    ("Operational Disruption", "Negative", "news", "System outage grounds {co} flights nationwide for six hours"),
    ("Operational Disruption", "Negative", "news", "Port congestion and supply chain bottlenecks delay {co} shipments"),
    ("Operational Disruption", "Negative", "news", "{co} issues product recall after defects found in a key component"),
    ("Operational Disruption", "Negative", "news", "Flooding forces {co} to shut down two facilities"),
    ("Operational Disruption", "Positive", "news", "{co} resumes full production after resolving the supply disruption"),
    ("Operational Disruption", "Neutral", "news", "{co} schedules planned maintenance shutdown at one site; output guidance unchanged"),
    ("Operational Disruption", "Negative", "news", "Power failure at {co} data centre causes a prolonged service outage"),
    ("Operational Disruption", "Negative", "social", "${tk} outage AGAIN. nothing works, customers furious"),
    ("Operational Disruption", "Negative", "social", "Strike at ${tk} looks like it will drag on. deliveries halted"),
    ("Operational Disruption", "Negative", "social", "Explosion reported at ${tk} facility, production stopped"),
    ("Operational Disruption", "Positive", "social", "${tk} production back to normal after the shutdown, good recovery"),
    ("Operational Disruption", "Neutral", "social", "${tk} maintenance shutdown this weekend, planned and announced"),

    # ---------------- Market / Liquidity ----------------
    ("Market / Liquidity", "Negative", "news", "Bond market sell-off deepens as funding stress spreads across the sector"),
    ("Market / Liquidity", "Negative", "news", "Credit spreads widen sharply as investors pull funds from high-yield markets"),
    ("Market / Liquidity", "Negative", "news", "Margin calls force hedge funds into fire sales, amplifying market volatility"),
    ("Market / Liquidity", "Negative", "news", "Depositors withdraw funds from {co} amid fears of a bank run"),
    ("Market / Liquidity", "Negative", "news", "Money market fund redemptions surge, draining liquidity from short-term funding markets"),
    ("Market / Liquidity", "Negative", "news", "Flash crash wipes {pct}% off equity indices before trading halt kicks in"),
    ("Market / Liquidity", "Positive", "news", "Liquidity conditions improve as repo rates normalise and spreads tighten"),
    ("Market / Liquidity", "Neutral", "news", "Market volatility index steady as trading volumes return to average levels"),
    ("Market / Liquidity", "Negative", "news", "Bid-ask spreads blow out in corporate bonds, {co} debt hardest hit"),
    ("Market / Liquidity", "Negative", "social", "Liquidity is gone. bonds gapping lower, nobody bidding"),
    ("Market / Liquidity", "Negative", "social", "Bank run vibes at ${tk}, long lines and app withdrawals frozen"),
    ("Market / Liquidity", "Negative", "social", "Huge outflows from credit funds today. spreads widening everywhere"),
    ("Market / Liquidity", "Positive", "social", "Funding markets calming down, spreads tightening. phew"),
    ("Market / Liquidity", "Negative", "social", "Margin calls everywhere this morning. forced selling into the close"),

    # ---------------- Unclassified / irrelevant ----------------
    ("Unclassified", "Neutral", "news", "{co} names a new head of investor relations effective next month"),
    ("Unclassified", "Neutral", "news", "{co} will present at an investor conference on Thursday"),
    ("Unclassified", "Positive", "news", "{co} sponsors local charity marathon for the fifth consecutive year"),
    ("Unclassified", "Neutral", "news", "{co} moves its annual general meeting to a new venue"),
    ("Unclassified", "Neutral", "news", "{co} publishes its annual sustainability report"),
    ("Unclassified", "Positive", "news", "{co} wins an award for workplace culture"),
    ("Unclassified", "Neutral", "news", "{co} updates its corporate logo and website design"),
    ("Unclassified", "Neutral", "social", "Anyone going to the ${tk} investor day? looking for a coffee meetup"),
    ("Unclassified", "Positive", "social", "Love the new ${tk} office design, looks great"),
    ("Unclassified", "Neutral", "social", "${tk} chart looking sideways for weeks. boring"),
    ("Unclassified", "Neutral", "social", "What time does the ${tk} webcast start?"),
    ("Unclassified", "Positive", "social", "Great customer service from ${tk} today, thanks team"),
    ("Unclassified", "Neutral", "social", "Reading about ${tk} history over the weekend, interesting company"),
]

PRODUCTS = ["AI accelerator chip", "payments app", "5G network service", "cloud platform", "oncology drug",
            "smart grid service", "fleet management system", "trading platform", "loyalty programme"]
REGIONS = ["the Eastern Corridor", "the Northern Gulf", "a key shipping strait", "the southern border region",
           "the Western Straits"]
AMOUNTS = ["$85 million", "$120 million", "$450 million", "$1.2 billion", "$2.4 billion"]
PCTS = [3, 5, 7, 8, 12, 15, 18, 22]
BPS = [25, 50, 75, 100]
QUARTERS = ["Q1", "Q2", "Q3", "Q4"]

# Hand-written showcase records included verbatim in the bundled samples (deterministic demo).
HERO_NEWS = [
    ("2026-10-02T07:15:00Z", "Synthetic Wire", "Sanctions escalate as military conflict spreads near a key shipping strait",
     "Global markets slide and oil surges as the embargo on a major exporter widens; Meridian Shipping and Helix "
     "Energy Corp flag severe disruption to routes and supply."),
    ("2026-10-01T13:40:00Z", "Synthetic Credit Desk", "Meridian Shipping missed a coupon payment on its senior bonds",
     "Rating agency downgrades Meridian Shipping to CCC and places it on negative watch, citing default risk and "
     "covenant breach as creditors prepare restructuring talks."),
    ("2026-09-30T09:05:00Z", "Synthetic Wire", "Ransomware attack forces Quantum Payments to halt card processing nationwide",
     "Hackers gained unauthorized access to core systems and customer data was exposed; regulators have been notified."),
    ("2026-09-29T15:30:00Z", "Synthetic Markets Desk", "Bond market sell-off deepens as funding stress spreads across the sector",
     "Credit spreads widen sharply, margin calls force fire sales and liquidity in corporate bonds evaporates."),
    ("2026-09-28T12:00:00Z", "Synthetic Wire", "Central bank delivers surprise 75 basis point rate hike",
     "Inflation hits 7.4%, the highest in a decade, and policymakers signal further monetary tightening as recession "
     "risk for the economy grows."),
    ("2026-09-27T10:20:00Z", "Synthetic Wire", "Aurora Semiconductors unveils next-generation AI accelerator chip",
     "The new product line launches in three markets with strong pre-orders, the company said."),
]
