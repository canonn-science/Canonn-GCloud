# Nearest 

This collection of scripts creates an index from the spansh galaxy stations dump and then loads that ito a google cloud function that can be used to locate the nearest thing of interest 

## \<root\>/services/\<key\>/\<ship\>

`ship`: size of landing pad needed; one of `S`, `M`, or `L`.

This function will locate the nearest service for the following keys

    apex_interstellar | apex
    autodock
    bartender
    black_market | blackmarket
    carrier_administration | module_packs
    carrier_vendor | fleet_carrier_vendor
    commodities | market
    contacts
    crew_lounge
    dock
    docking
    flight_controller
    frontline_solutions | frontline
    interstellar_factors | facilitator | factor
    livery
    material_trader | encoded_material_trader | raw_material_trader | manufactured_material_trader
        raw_mats | encoded_mats | manufactured_mats
    missions
    missions_generated
    on_dock_mission
    outfitting
    pioneer_supplies
    powerplay
    rearm | restock
    redemption_office
    refuel
    repair
    search_and_rescue | snr | s_and_r | search | resuce
    shipyard
    shop
    social_space
    station_menu
    station_operations
    technology_broker | guardian_technology_broker | human_technology_broker
    tuning
    universal_cartographics | cartographics | carto
    vista_genomics | vista | genomics
    workshop


