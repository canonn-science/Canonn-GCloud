create or replace view v_nhsssystems_limits as 
SELECT MIN(
    (
        CASE WHEN (
            (`data`.`sol` < `data`.`merope`) AND 
            (`data`.`sol` < `data`.`coalsack`) AND 
            (`data`.`sol` < `data`.`california`) AND 
            (`data`.`sol` < `data`.`conesector`) AND             
            (`data`.`sol` < `data`.`witchhead`)
            ) 
            THEN `data`.`sol` 
        END)
    ) AS `min_sol`, 
    MAX(
        (CASE WHEN (
            (`data`.`merope` < `data`.`sol`) AND 
            (`data`.`merope` < `data`.`coalsack`) AND 
            (`data`.`merope` < `data`.`california`) AND 
            (`data`.`merope` < `data`.`conesector`) AND                         
            (`data`.`merope` < `data`.`witchhead`))
            THEN `data`.`merope` 
        END)
        ) AS `max_merope`, 
    MAX(
        (CASE WHEN (
            (`data`.`coalsack` < `data`.`sol`) AND 
            (`data`.`coalsack` < `data`.`merope`) AND 
            (`data`.`coalsack` < `data`.`witchhead`)) AND
            (`data`.`coalsack` < `data`.`conesector`) AND                             
            (`data`.`coalsack` < `data`.`california`) 
            THEN `data`.`coalsack` END)
        ) AS `max_coalsack`, 
    MAX(
        (CASE WHEN (
            (`data`.`witchhead` < `data`.`sol`) AND 
            (`data`.`witchhead` < `data`.`merope`) AND 
            (`data`.`witchhead` < `data`.`california`) AND 
            (`data`.`witchhead` < `data`.`conesector`) AND                             
            (`data`.`witchhead` < `data`.`coalsack`)) 
            THEN `data`.`witchhead` 
        END)
        ) AS `max_witchhead`,
    MAX(
        (CASE WHEN (
            (`data`.`california` < `data`.`sol`) AND 
            (`data`.`california` < `data`.`merope`) AND 
            (`data`.`california` < `data`.`witchhead`) AND 
            (`data`.`california` < `data`.`conesector`) AND                             
            (`data`.`california` < `data`.`coalsack`)) 
            THEN `data`.`california` 
        END)
        ) AS `max_california`,
    MAX(
        (CASE WHEN (
            (`data`.`conesector` < `data`.`sol`) AND 
            (`data`.`conesector` < `data`.`merope`) AND 
            (`data`.`conesector` < `data`.`witchhead`) AND 
            (`data`.`conesector` < `data`.`california`) AND                             
            (`data`.`conesector` < `data`.`coalsack`)) 
            THEN `data`.`conesector` 
        END)
        ) AS `max_conesector`            
FROM (
SELECT 
    `canonn`.`nhsssystems`.`systemName` AS `systemName`,
    `canonn`.`nhsssystems`.`x` AS `x`,
    `canonn`.`nhsssystems`.`y` AS `y`,
    `canonn`.`nhsssystems`.`z` AS `z`, 
    SQRT(((POW((`canonn`.`nhsssystems`.`x` - -(78.59375)),2) + POW((`canonn`.`nhsssystems`.`y` - -(149.625)),2)) + POW((`canonn`.`nhsssystems`.`z` - -(340.53125)),2))) AS `merope`, 
    SQRT(((POW((`canonn`.`nhsssystems`.`x` - 423.5625),2) + POW((`canonn`.`nhsssystems`.`y` - 0.5),2)) + POW((`canonn`.`nhsssystems`.`z` - 277.75),2))) AS `coalsack`, 
    SQRT(((POW((`canonn`.`nhsssystems`.`x` - 355.75),2) + POW((`canonn`.`nhsssystems`.`y` - -(400.5)),2)) + POW((`canonn`.`nhsssystems`.`z` - -(707.21875)),2))) AS `witchhead`, 
    SQRT(((POW((`canonn`.`nhsssystems`.`x` - -299.0625),2) + POW((`canonn`.`nhsssystems`.`y` - -229.25),2)) + POW((`canonn`.`nhsssystems`.`z` - -876.125),2))) AS `california`, 
    SQRT(((POW((`canonn`.`nhsssystems`.`x` - 609.4375),2) + POW((`canonn`.`nhsssystems`.`y` - 154.25),2)) + POW((`canonn`.`nhsssystems`.`z` - -1503.59375),2))) AS `conesector`, 
    SQRT(((POW((`canonn`.`nhsssystems`.`x` - 0),2) + POW((`canonn`.`nhsssystems`.`y` - 0),2)) + POW((`canonn`.`nhsssystems`.`z` - 0),2))) AS `sol`
FROM `canonn`.`nhsssystems`) `data`;