local out_dir = os.getenv("MERMAID_OUT") or "."
local puppeteer = os.getenv("MERMAID_PUPPETEER")
local count = 0

local function shquote(s)
  return "'" .. s:gsub("'", "'\\''") .. "'"
end

function CodeBlock(block)
  if not block.classes:includes("mermaid") then return nil end
  count = count + 1
  local stem = out_dir .. "/diagram-" .. count
  local mmd, png = stem .. ".mmd", stem .. ".png"
  local fh = io.open(mmd, "w")
  if not fh then return nil end
  fh:write(block.text)
  fh:close()
  local pflag = puppeteer and puppeteer ~= ""
    and " -p " .. shquote(puppeteer) or ""
  local cmd = "mmdc -i " .. shquote(mmd) .. " -o " .. shquote(png)
    .. " -b white -s 2" .. pflag .. " >/dev/null 2>&1"
  if not os.execute(cmd) then return nil end
  return pandoc.Para({ pandoc.Image({}, png) })
end
