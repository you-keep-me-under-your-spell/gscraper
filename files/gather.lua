local BaseUrl = "http://localhost:4920"
local PlaceId = game.PlaceId
local PlaceAssoc = {}

local Players = game:GetService("Players")
local RS = game:GetService("ReplicatedStorage")
local HS = game:GetService("HttpService")
repeat wait() until Players.LocalPlayer
local player = Players.LocalPlayer

local function postResult(result)
    local data = {userId=player.UserId, result=result}
    data = HS:JSONEncode(data)
    local resp = syn.request({
        Method = "POST",
        Url = BaseUrl .. "/result",
        Headers = {["Content-Type"] = "application/json; charset=UTF-8"},
        Body = data
    })

    if resp.StatusCode ~= 200 then
        return warn("Error with postResult")
    end
end

-- Adopt Me
local function collectAdoptMeInfo()
    local result = {
        money = 0,
        pets = {},
        toys = {}
    }
    local PetsDB = require(RS:WaitForChild("ClientDB"):WaitForChild("Inventory"):WaitForChild("InventoryPetsSubDB"))
    local ToysDB = require(RS:WaitForChild("ClientDB"):WaitForChild("Inventory"):WaitForChild("InventoryToysSubDB"))
    local RarityDB = require(RS:WaitForChild("ClientDB"):WaitForChild("RarityDB"))
    local Router = require(RS:WaitForChild("ClientModules"):WaitForChild("Core"):WaitForChild("RouterClient"):WaitForChild("RouterClient"))
    local ServerData
    local PlayerInfo

    while 1 do
        ServerData = Router.get_event("DataAPI/GetAllServerData"):InvokeServer()
        PlayerInfo = ServerData[player.Name]
        if PlayerInfo and PlayerInfo.inventory and PlayerInfo.inventory.pets and PlayerInfo.inventory.toys then
            break
        end
        wait(0.5)
    end

    result.money = PlayerInfo.money

    -- load pets
    local model, name, mega, neon, rideable, flyable, code, row, rarity
    for _, pet in pairs(PlayerInfo.inventory.pets) do
        model = PetsDB[pet.id]
        name = model.name
        rarity = RarityDB[model.rarity].name
        rideable = pet.properties.rideable and "R"
        flyable = pet.properties.flyable and "F"
        neon = pet.properties.neon and "N"
        mega = pet.properties.mega or pet.properties.mega_neon
        mega = mega and "M"

        code = ("%s%s%s"):format(
            (mega or neon) or "",
            flyable or "",
            rideable or ""
        )

        row = ("%s (%s)[%s]"):format(
            name,
            rarity,
            code
        )
        table.insert(result.pets, row)
    end

    -- load toys
    local model, name, row, rarity
    for _, toy in pairs(PlayerInfo.inventory.toys) do
        model = ToysDB[toy.id]
        name = model.name
        rarity = RarityDB[model.rarity].name

        row = ("%s (%s)"):format(
            name,
            rarity
        )
        table.insert(result.toys, row)
    end
    return result
end
PlaceAssoc[920587237] = collectAdoptMeInfo
------------------------------------------------------
------------------------------------------------------
local function collectJailbreakInfo()
    local result = {money=0}

    local money
    while 1 do
        money = player:FindFirstChild("leaderstats") and player.leaderstats:FindFirstChild("Money").Value
        if money then
            break
        end
    end
    result.money = money
    return result
end
PlaceAssoc[606849621] = collectJailbreakInfo
------------------------------------------------------
------------------------------------------------------
local function collectCbroInfo()
    local values = HS:JSONDecode(syn.request({Method="GET",Url="https://pastebin.com/raw/dbRTNWVX"}).Body)
    local result = {cash=0,funds=0,skins={},value=0}
    repeat wait() until player:FindFirstChild("SkinFolder") and player.SkinFolder:FindFirstChild("Funds")
    local rarities = game:GetService("StarterGui"):WaitForChild("Client"):WaitForChild("Rarities")
    result.funds = player.SkinFolder.Funds.Value
    result.cash = player:WaitForChild("Cash").Value

    local full, weapon, skin, row, rarity, value
    for _, full in pairs(game.ReplicatedStorage.GetInventory:InvokeServer()) do
        full = full[1]
        v = full:split("_")
        weapon = v[1]
        skin = v[2]
        if skin ~= "Stock" then
            rarity = rarities:WaitForChild(full).Value
            value = values[full] or 0
            result.value += value
            row = ("%s - %s (%s, %d)"):format(
                weapon, skin, rarity, value
            )
            table.insert(result.skins, row)
        end
    end
    return result
end
PlaceAssoc[301549746] = collectCbroInfo
------------------------------------------------------

local payload = PlaceAssoc[PlaceId]
if not payload then
    error(("Payload was not found for place %d"):format(PlaceId))
end

local result = payload()
--print(HS:JSONEncode(result))
postResult(result)