import json
import io
from datetime import date
from pathlib import Path

TotalByteCount = 0
EEPROM_Count = 0
PageCount = 0

today = date.today()

script_dir = Path(__file__).resolve().parent
module_dir = script_dir.parent

code_header = (script_dir / 'header.h').read_text()
code_header = code_header.replace("<today>", today.strftime("%b-%d-%Y"))
code_header = code_header.replace("<year>", today.strftime("%Y"))

#eeprom_status_check = "get_eeprom_status() == EEPROM_STATUS_PRESENT"
eeprom_status_check = "true"

# Open the command list
with (script_dir / 'config.json').open() as f:
  config = json.load(f)

print("\n---- GENERATING SETTINGS ----\n")

max_views = config["config"]["max_views"]
print("Number of views: " + str(max_views))

max_gauges_per_view = config["config"]["max_gauges_per_view"]
print("Max gauges per view: " + str(max_gauges_per_view))

max_alerts = config["config"]["max_alerts"]
print("Max Alerts: " + str(max_alerts))

alert_message_len = config["config"]["alert_message_len"]
print("Alert_Message_Len: " + str(alert_message_len))

max_dynamics = config["config"]["max_dynamics"]
print("max_dynamics: " + str(max_dynamics))

max_generals = config["config"]["max_generals"]
print("max_generals: " + str(max_generals))

# Generate in memory so an exception cannot leave partially-written C files.
config_c = io.StringIO()
config_h = io.StringIO()

config_c.write( code_header + "\n\n" )
config_h.write( code_header + "\n\n" )

config_h.write("#ifndef KE_CONFIG_H\n")
config_h.write("#define KE_CONFIG_H\n\n")
config_h.write("#ifdef __cplusplus\n")
config_h.write("extern \"C\"\n{\n")
config_h.write("#endif\n\n")

config_h.write("#include <stdbool.h>\n")
config_h.write("#include <string.h>\n")
config_h.write("#include <stdlib.h>\n")
config_h.write("#include \"cJSON.h\"\n")
config_h.write("#include \"lib_pid.h\"\n\n")

config_h.write("typedef void(settings_write)(uint16_t bAdd, uint8_t bData);\n")
config_h.write("typedef uint8_t(settings_read)(uint16_t bAdd);\n\n")

config_h.write("void settings_setWriteHandler(settings_write *writeHandler);\n")
config_h.write("void settings_setReadHandler(settings_read *readHandler);\n\n")

config_h.write(f"#define MAX_GAUGES_PER_VIEW {max_gauges_per_view}\n")
config_h.write(f"#define MAX_ALERTS {max_alerts}\n")
config_h.write(f"#define ALERT_MESSAGE_LEN {alert_message_len}\n")
config_h.write(f"#define MAX_VIEWS {max_views}\n")
config_h.write(f"#define MAX_DYNAMICS {max_dynamics}\n")
config_h.write(f"#define MAX_GENERALS {max_generals}")

config_c.write( "#include \"ke_config.h\"\n" )
config_c.write( "#include \"cjson_shared.h\"\n\n" )
config_c.write( "#include <math.h>\n\n" )

def get_eeprom_size(cmd: dict) -> int:
    size = cmd.get("EEBytes")
    if isinstance(size, int):
        return size
    elif isinstance(size, str):
        return config["config"].get(size, 0)  # Or raise an error
    else:
        raise TypeError("EEBytes must be int or str")

def get_total_eeprom_size() -> int:
    total = 0
    for struct_entry in config["config"]["struct_list"]:
        for parent_struct, sub_structs in struct_entry.items():
            for cmd in config[parent_struct]:
                count = config["config"][cmd["count"]] if cmd["index"] else 1
                total += get_eeprom_size(cmd) * count
            for sub_struct in sub_structs:
                for cmd in config[sub_struct]:
                    if cmd["index"]:
                        count = (config["config"][cmd["count"][0]] *
                                 config["config"][cmd["count"][1]])
                    else:
                        count = 1
                    total += get_eeprom_size(cmd) * count
    return total

def validate_config() -> None:
    allowed_types = {"number", "slider", "list", "string"}
    fixed_sizes = {"uint8_t": 1, "uint16_t": 2, "uint32_t": 4, "float": 4}

    for struct_entry in config["config"]["struct_list"]:
        for parent_struct, sub_structs in struct_entry.items():
            for struct_name in [parent_struct, *sub_structs]:
                if struct_name not in config:
                    raise ValueError(f"missing settings section: {struct_name}")

                for cmd in config[struct_name]:
                    label = f"{struct_name}.{cmd.get('cmd', '<unnamed>')}"
                    setting_type = cmd.get("type")
                    if setting_type not in allowed_types:
                        raise ValueError(f"{label}: unsupported type {setting_type!r}")

                    ee_size = get_eeprom_size(cmd)
                    if ee_size <= 0:
                        raise ValueError(f"{label}: EEBytes must resolve to a positive integer")

                    expected_size = fixed_sizes.get(cmd.get("dataType"))
                    if setting_type != "string" and expected_size and ee_size != expected_size:
                        raise ValueError(
                            f"{label}: EEBytes is {ee_size}, expected {expected_size} "
                            f"for {cmd['dataType']}"
                        )

                    if cmd.get("index"):
                        counts = cmd.get("count")
                        counts = counts if isinstance(counts, list) else [counts]
                        if not counts or any(
                            count not in config["config"] or config["config"][count] <= 0
                            for count in counts
                        ):
                            raise ValueError(f"{label}: invalid count reference")
                        if setting_type == "string" and len(counts) != 1:
                            raise ValueError(f"{label}: two-dimensional strings are not supported")
                    else:
                        raise ValueError(f"{label}: non-indexed settings are not supported")

                    if setting_type in ("number", "slider"):
                        if "min" not in cmd or "max" not in cmd:
                            raise ValueError(f"{label}: numeric settings require min and max")
                        if isinstance(cmd["min"], (int, float)) and isinstance(cmd["max"], (int, float)):
                            if cmd["min"] > cmd["max"]:
                                raise ValueError(f"{label}: min exceeds max")
                            default = cmd.get("default")
                            if isinstance(default, (int, float)):
                                upper_ok = default < cmd["max"] if cmd.get("maxExclusive") else default <= cmd["max"]
                                if default < cmd["min"] or not upper_ok:
                                    raise ValueError(f"{label}: default is outside its valid range")

                    elif setting_type == "list":
                        if not cmd.get("options") or cmd.get("default") not in cmd["options"]:
                            raise ValueError(f"{label}: list default must be one of its options")
                        if not cmd.get("limit"):
                            raise ValueError(f"{label}: list settings require a limit enum")

                    elif setting_type == "string":
                        default = cmd.get("default", "")
                        if not (isinstance(default, str) and len(default) >= 2 and default[0] == '"' and default[-1] == '"'):
                            raise ValueError(f"{label}: string default must be a C string literal")
                        if len(default[1:-1]) >= ee_size:
                            raise ValueError(f"{label}: string default does not fit in EEBytes")

settings_byte_count = get_total_eeprom_size()
validate_config()

eeprom_device = config["config"]["eeprom_device"]
eeprom_capacity_kbit = config["config"]["eeprom_capacity_kbit"]
i2c_clock_hz = config["config"]["i2c_clock_hz"]
write_cycle_typical_ms = config["config"]["eeprom_write_cycle_typical_ms"]
write_cycle_max_ms = config["config"]["eeprom_write_cycle_max_ms"]
eeprom_capacity_bytes = eeprom_capacity_kbit * 1024 // 8

if settings_byte_count > eeprom_capacity_bytes:
    raise ValueError(
        f"generated settings map ({settings_byte_count}) exceeds EEPROM capacity "
        f"({eeprom_capacity_bytes})"
    )

# HAL_I2C_Mem_Read with a 16-bit memory address performs five 9-clock byte
# transfers: control(write), two address bytes, control(read), and one data byte.
read_clocks_per_byte = 5 * 9
load_time_seconds = settings_byte_count * read_clocks_per_byte / i2c_clock_hz

# The current erase implementation performs one HAL write per byte. Each call
# first checks readiness (one control byte), then transfers control + two address
# bytes + one data byte. The internal write cycle follows every byte write.
erase_clocks_per_byte = (1 + 4) * 9
erase_bus_time_seconds = settings_byte_count * erase_clocks_per_byte / i2c_clock_hz
erase_typical_seconds = erase_bus_time_seconds + (
    settings_byte_count * write_cycle_typical_ms / 1000
)
erase_max_seconds = erase_bus_time_seconds + (
    settings_byte_count * write_cycle_max_ms / 1000
)

def write_stats_readme() -> None:
    used_percent = settings_byte_count / eeprom_capacity_bytes * 100
    free_bytes = eeprom_capacity_bytes - settings_byte_count
    i2c_khz = i2c_clock_hz / 1000

    readme = f"""# Generated Settings Statistics

This file is generated by `generate-settings.py`. Do not edit it manually.

## EEPROM

| Statistic | Value |
| --- | ---: |
| Device | {eeprom_device} |
| Capacity | {eeprom_capacity_kbit} Kbit ({eeprom_capacity_bytes:,} bytes) |
| I2C clock | {i2c_khz:g} kHz |
| Generated settings data | {settings_byte_count:,} bytes ({used_percent:.2f}%) |
| Unreserved EEPROM | {free_bytes:,} bytes |

## Estimated Timing

| Operation | Estimate |
| --- | ---: |
| Load all generated settings | {load_time_seconds * 1000:.1f} ms |
| Mass erase, typical | {erase_typical_seconds:.2f} s |
| Mass erase, maximum write-cycle rating | {erase_max_seconds:.2f} s |

### Load calculation

`load_settings()` reads {settings_byte_count} bytes individually. A one-byte random read with a
16-bit address transfers five I2C bytes (control-write, two address bytes,
control-read, and data). Including ACK/NACK bits, that is 45 SCL clocks:

`{settings_byte_count} bytes * 45 clocks / {i2c_clock_hz:,} Hz = {load_time_seconds * 1000:.1f} ms`

### Mass erase calculation

`settings_erase_eeprom()` performs {settings_byte_count} separate byte writes. The current driver
does a readiness check followed by a four-byte write transaction, totaling about
45 SCL clocks per byte, and waits for the EEPROM's internal write cycle after
every byte:

- I2C bus time: `{settings_byte_count} * 45 / {i2c_clock_hz:,} = {erase_bus_time_seconds * 1000:.1f} ms`
- Typical: `{erase_bus_time_seconds:.4f} s + {settings_byte_count} * {write_cycle_typical_ms} ms = {erase_typical_seconds:.2f} s`
- Maximum: `{erase_bus_time_seconds:.4f} s + {settings_byte_count} * {write_cycle_max_ms} ms = {erase_max_seconds:.2f} s`

These are protocol estimates. STM32 HAL/software overhead and additional ACK
polls can make measured times slightly longer. The {write_cycle_typical_ms} ms typical and {write_cycle_max_ms} ms maximum internal
write-cycle values are the timing assumptions for the {eeprom_device}.
"""
    (script_dir / "README.md").write_text(readme, newline="\n")

def write_default_define(file, prefix, cmd, depth):
    print(f"[ADDED] {cmd['name']}")

    define_name = f"DEFAULT_{prefix.upper()}_{cmd['cmd'].upper()}"

    raw_default = cmd["default"]
    default = str(raw_default)
    if cmd["type"] == "string":
        value = default
    elif isinstance(raw_default, (int, float)):
        value = default
    else:
        data_type = cmd["dataType"].replace(" ", "_").upper()
        default_value = default.replace(" ", "_").upper()
        value = f"{data_type}_{default_value}"

    file.write(f"#define {define_name} {value}\n")

def write_size_define(file, prefix, cmd, depth):
    define_name = f"EE_SIZE_{prefix.upper()}_{cmd['cmd'].upper()}"

    ee_bytes = cmd["EEBytes"]
    value = str(ee_bytes) if str(ee_bytes).isnumeric() else str(ee_bytes).upper()

    file.write(f"#define {define_name} {value}\n")

def write_comment_block(file, prefix, cmd, depth):
    file.write("\n\n")
    file.write("/********************************************************************************\n")
    file.write(f"*{cmd['name'].center(79)}\n")
    file.write("*\n")

    if cmd["index"]:
        parts = prefix.split('_')
        if depth == 2 and len(parts) >= 2:
            file.write(f"* @param idx_{parts[0].lower()}    index of the {parts[0]}\n")
            file.write(f"* @param idx_{parts[1].lower()}    index of the {parts[1]}\n")
        else:
            file.write(f"* @param idx_{prefix.lower()}    index of the {prefix}\n")

    file.write(f"* @param {cmd['cmd']}    {cmd['desc']}\n")
    file.write("* @param save    Set true to save to the EEPROM, otherwise value is non-volatile\n")
    file.write("*\n")
    file.write("********************************************************************************/\n")

def write_custom_struct(file, prefix, cmd, depth):
    if cmd["type"] == "list":
        enum_type = cmd["dataType"]
        file.write("typedef enum\n{\n")

        for option in cmd["options"]:
            enum_name = f"{enum_type}_{option.replace(' ', '_').upper()}"
            file.write(f"    {enum_name},\n")

        limit_name = f"{enum_type}_{cmd['limit'].replace(' ', '_').upper()}"
        file.write(f"    {limit_name}\n")
        file.write(f"}} {enum_type};\n\n")

def write_array_string_def_extern(file, prefix, cmd, depth):
    if cmd["type"] == "list":
        array_name = f'{cmd["dataType"].lower()}_string'
        file.write(f"extern const char *{array_name}[];\n")

def write_array_string_def(file, prefix, cmd, depth):
    if cmd["type"] == "list":
        array_name = f'{cmd["dataType"].lower()}_string'
        file.write(f"const char *{array_name}[] = {{\n")

        for i, option in enumerate(cmd["options"]):
            comma = "," if i < len(cmd["options"]) - 1 else ""
            file.write(f'    "{option}"{comma}\n')

        file.write("};\n\n")

def write_verify_declare( file, prefix, cmd, depth ):
    if( cmd["type"] == "string" ):
       pointer = "*"
    else:
       pointer = ""
    file.write( "bool verify_" + prefix + "_" + cmd["cmd"].lower() + "(" + cmd["dataType"] + pointer + " " + cmd["cmd"].lower() + ");\n" )

def write_verify_source( file, prefix, cmd, depth ):
    if( cmd["type"] == "string" ):
       pointer = "*"
    else:
       pointer = ""

    input = prefix.lower() + "_" + cmd["cmd"].lower()
    file.write( "bool verify_" + prefix + "_" + cmd["cmd"].lower() + "(" + cmd["dataType"] + pointer + " " + input + ")\n" )
    file.write( "{\n" )
    if cmd["type"] == "number" or cmd["type"] == "slider":
      minimum = str(cmd["min"]).upper()
      maximum = str(cmd["max"]).upper()

      if cmd["dataType"] == "float":
          file.write("    if (!isfinite(" + input + "))\n")
          file.write("        return false;\n\n")

      lower_check_omitted = (
          ("uint" in cmd["dataType"] or cmd["dataType"] == "PID_UNITS")
          and cmd["min"] == 0
      )
      if not lower_check_omitted:
          file.write("    if (" + input + " < " + minimum + ")\n")
          file.write("        return false;\n\n")

      type_maximums = {"uint8_t": 255, "uint16_t": 65535, "uint32_t": 4294967295}
      full_type_range = (
          not cmd.get("maxExclusive", False)
          and type_maximums.get(cmd["dataType"]) == cmd["max"]
      )
      if not full_type_range:
          comparison = ">=" if cmd.get("maxExclusive", False) else ">"
          file.write("    if (" + input + " " + comparison + " " + maximum + ")\n")
          file.write("        return false;\n\n")
      if lower_check_omitted and full_type_range:
          file.write("    (void)" + input + ";\n\n")
      file.write("    return true;")

    elif cmd["type"] == "list":
        file.write("    if (" + input + " >= " + cmd["dataType"] + "_" + cmd["limit"].replace(" ", "_").upper() + ")\n" )
        file.write("        return false;\n\n" )
        file.write("    return true;" )

    elif cmd["type"] == "pointer":
        file.write("    return " + input + " != " +  str(cmd["limit"]) + ";" )

    elif cmd["type"] == "string":
        size = "EE_SIZE_" + prefix.upper() + "_" + cmd["cmd"].upper()
        file.write("    return (" + input + " != NULL) &&\n")
        file.write("           (memchr(" + input + ", '\\0', " + size + ") != NULL);" )
       

    file.write("\n}\n\n")

def write_get_source(file, prefix, cmd, depth):
    if( cmd["type"] == "string" ):
      if( cmd["index"] ):
        if( depth == 2 ):
            input = "uint8_t idx_" + prefix.lower().split('_')[0] + ", uint8_t idx_" + prefix.lower().split('_')[1] + ", " + cmd["dataType"] + "* " + prefix + "_" + cmd["cmd"].lower()
            index = "[idx_" + prefix.lower().split('_')[0] + "][idx_" + prefix.lower().split('_')[1] + "]"
        else:
            input = "uint8_t idx, " + cmd["dataType"] + "* " + prefix + "_" + cmd["cmd"].lower()
            index = "[idx]"
      else:
        input = "void"
        index = ""

      output = "settings_" + prefix + "_" + cmd["cmd"].lower() + index

      file.write("void get_" + prefix + "_" + cmd["cmd"].lower() + "(" + input + ")\n{\n")
      output_arg = prefix + "_" + cmd["cmd"].lower()
      file.write("    if (" + output_arg + " == NULL)\n")
      file.write("        return;\n\n")
      if cmd["index"]:
        if depth == 2:
          first, second = prefix.lower().split('_')[:2]
          bounds = f"(idx_{first} >= {cmd['count'][0].upper()}) || (idx_{second} >= {cmd['count'][1].upper()})"
        else:
          bounds = f"idx >= {cmd['count'].upper()}"
        file.write("    if (" + bounds + ")\n")
        file.write("    {\n")
        file.write("        " + output_arg + "[0] = '\\0';\n")
        file.write("        return;\n")
        file.write("    }\n\n")
      file.write("    memcpy(" + prefix + "_" + cmd["cmd"].lower() + ", " + output + ", " + str(cmd["EEBytes"]).upper() + ");\n")
      file.write("    " + prefix + "_" + cmd["cmd"].lower() + "[" + str(cmd["EEBytes"]).upper() + " - 1] = '\\0';\n")

      file.write("}\n\n")
    else:
      if( cmd["index"] ):
        if( depth == 2 ):
            input = "uint8_t idx_" + prefix.lower().split('_')[0] + ", uint8_t idx_" + prefix.lower().split('_')[1]
            index = "[idx_" + prefix.lower().split('_')[0] + "][idx_" + prefix.lower().split('_')[1] + "]"
        else:
            input = "uint8_t idx"
            index = "[idx]"
      else:
        input = "void"
        index = ""

      file.write(cmd["dataType"] + " get_" + prefix + "_" + cmd["cmd"].lower() + "(" + input + ")\n{\n")

      output = "settings_" + prefix + "_" + cmd["cmd"].lower() + index

      if cmd["index"]:
        if depth == 2:
          first, second = prefix.lower().split('_')[:2]
          bounds = f"(idx_{first} >= {cmd['count'][0].upper()}) || (idx_{second} >= {cmd['count'][1].upper()})"
        else:
          bounds = f"idx >= {cmd['count'].upper()}"
        file.write("    if (" + bounds + ")\n")
        file.write("        return DEFAULT_" + prefix.upper() + "_" + cmd["cmd"].upper() + ";\n\n")

      file.write("    // Verify the " + cmd["name"] + " value is valid\n")
      file.write("    if (!verify_" + prefix + "_" + cmd["cmd"].lower() + "(" + output + "))\n")
      file.write("        return DEFAULT_" + prefix.upper() + "_" + cmd["cmd"].upper() + ";\n\n" )

      file.write("    return " + output + ";\n")
      file.write("}\n\n")

def write_string_compare_declare(file, prefix, cmd, depth):
   if( cmd["type"] == "list" ):
    file.write( cmd["dataType"].upper() + " get_" + prefix + "_" + cmd["cmd"].lower() + "_from_string(const char *str);\n")

def write_string_compare(file, prefix, cmd, depth):
      if( cmd["type"] == "list" ):
        file.write( "\n" + cmd["dataType"].upper() + " get_" + prefix + "_" + cmd["cmd"].lower() + "_from_string(const char *str)\n{\n")
        file.write("    if (str == NULL) return " + cmd["dataType"].upper() + "_RESERVED;\n")
        for enum in cmd["options"]:
          file.write("    if(strcmp(str, \"" + enum + "\") == 0) return " + cmd["dataType"] + "_" + enum.replace(" ", "_").upper() + ";\n")

        file.write("    return " + cmd["dataType"].upper() + "_RESERVED" + ";\n")
        file.write("}\n\n")

def write_set_source(file, prefix, cmd, depth):
    if( cmd["type"] == "string" ):
       pointer = "*"
    else:
       pointer = ""

    if( cmd["index"] ):
      if( depth == 2 ):
          input = "uint8_t idx_" + prefix.lower().split('_')[0] + ", uint8_t idx_" + prefix.lower().split('_')[1] + ", " + cmd["dataType"] + pointer + " " + prefix.lower() + "_" + cmd["cmd"].lower()
          index = "idx_" + prefix.lower().split('_')[0] + ", idx_" + prefix.lower().split('_')[1]
          var = "[idx_" + prefix.lower().split('_')[0] + "][idx_" + prefix.lower().split('_')[1] + "]"
          output = "settings_" + prefix + "_" + cmd["cmd"].lower() + "[idx_" + prefix.lower().split('_')[0] + "][idx_" + prefix.lower().split('_')[1] + "]"
      else:
          input = "uint8_t idx, " + cmd["dataType"] + pointer + " " + prefix.lower() + "_" + cmd["cmd"].lower()
          index = "idx"
          var = "[idx]"
          output = "settings_" + prefix + "_" + cmd["cmd"].lower() + "[idx]"
    else:
       input = "void"
       index = ""
       output = output = "settings_" + prefix + "_" + cmd["cmd"].lower()


    file.write("// Set the " + cmd["name"] + "\n")
    file.write("bool set_" + prefix.lower() + "_" + cmd["cmd"].lower() + "(" + input + ", bool save)\n{\n")

    if cmd["index"]:
      if depth == 2:
        first, second = prefix.lower().split('_')[:2]
        bounds = f"(idx_{first} >= {cmd['count'][0].upper()}) || (idx_{second} >= {cmd['count'][1].upper()})"
      else:
        bounds = f"idx >= {cmd['count'].upper()}"
      file.write("    if (" + bounds + ")\n")
      file.write("        return false;\n\n")

    file.write("    // Verify the " + cmd["name"] + " value is valid\n")
    file.write("    if (!verify_" + prefix.lower() + "_" + cmd["cmd"].lower() + "(" + prefix.lower() + "_" + cmd["cmd"].lower() + "))\n")
    file.write("        return false;\n\n")

    if cmd["type"] == "string":
      size = "EE_SIZE_" + prefix.upper() + "_" + cmd["cmd"].upper()
      file.write("    " + cmd["dataType"] + " normalized[" + size + "] = {0};\n")
      file.write("    memcpy(normalized, " + prefix.lower() + "_" + cmd["cmd"].lower() + ", strlen(" + prefix.lower() + "_" + cmd["cmd"].lower() + "));\n\n")
    
    file.write("    // Check to see if the " + cmd["name"] + " EEPROM value needs to be\n")
    file.write("    // updated if immediate save is set\n")
    file.write("    if (save)\n    {\n")
    file.write("        // Reload the current setting saved in EEPROM\n")
    if( cmd["type"] == "string" ):
      file.write("        load_" + prefix + "_" + cmd["cmd"].lower() + "(" + index + ", " + output + ");\n\n")
      file.write("        if (memcmp(settings_" + prefix + "_" + cmd["cmd"].lower() + var + ", normalized, " + str(cmd["EEBytes"]).upper() + ") != 0)\n        {\n")
    else:
      file.write("        load_" + prefix + "_" + cmd["cmd"].lower() + "(" + index + ", &" + output + ");\n\n")
      file.write("        if (settings_" + prefix + "_" + cmd["cmd"].lower() + var + " != " + prefix.lower() + "_" + cmd["cmd"].lower() + ")\n        {\n")
    if( cmd["type"] == "string" ):
      file.write("            save_" + prefix + "_" + cmd["cmd"].lower() + "(" + index + ", normalized);\n")
    else:
      file.write("            save_" + prefix + "_" + cmd["cmd"].lower() + "(" + index + ", &" + prefix.lower() + "_" + cmd["cmd"].lower() + ");\n")
    file.write("        }\n")
    file.write("    }\n\n")

    if( cmd["type"] == "string" ):
      file.write("    memcpy(" + output + ", normalized, " + str(cmd["EEBytes"]).upper() + ");\n\n")
    else:
      file.write("    " + output + " = " + prefix.lower() + "_" + cmd["cmd"].lower() + ";\n\n")
    file.write("    return 1;\n" )
    file.write("}\n")

def write_get_declare( file, prefix, cmd, depth ):
    if( cmd["type"] == "string" ):
      if( cmd["index"] ):
        if( depth == 2 ):
            input = "uint8_t idx_" + prefix.lower().split('_')[0] + ", uint8_t idx_" + prefix.lower().split('_')[1] + ", " + cmd["dataType"] + "* " + prefix + "_" + cmd["cmd"].lower()
        else:
            input = "uint8_t idx, " + cmd["dataType"] + "* " + prefix + "_" + cmd["cmd"].lower()
      else:
        input = "void"

      file.write("void get_" + prefix + "_" + cmd["cmd"].lower() + "(" + input + ");\n")

    else:
      # Get function definition
      if cmd["index"]:
        if( depth == 2):
          func = "uint8_t idx_" + prefix.split('_')[0].lower() + ", uint8_t idx_" + prefix.split('_')[1].lower()
        else:
          func = "uint8_t idx_" + prefix.lower()
      else:
        func = "void"
      
      file.write( cmd["dataType"] + " get_" + prefix + "_" + cmd["cmd"].lower() + "(" + func + ");\n" )

def write_set_declare( file, prefix, cmd, depth ):
    if( cmd["type"] == "string" ):
       pointer = "*"
    else:
       pointer = ""
    # Set function definition
    if cmd["index"]:
      if( depth == 2):
        func = "uint8_t idx_" + prefix.split('_')[0].lower() + ", uint8_t idx_" + prefix.split('_')[1].lower() + ", "
      else:
         func = "uint8_t idx_" + prefix.lower() + ","
    else:
      func = ""

    func = func + " " + cmd["dataType"] + pointer + " " + cmd["cmd"].lower();

    file.write( "bool set_" + prefix + "_" + cmd["cmd"].lower() + "(" + func + ", bool save);\n" )

def sub_write_memory_organization( file, prefix, cmd, idx ):
  global PageCount, EEPROM_Count, TotalByteCount
  byte_count = 1
  #define EEPROM byte offset
  while byte_count <= get_eeprom_size(cmd):
    if( idx > 0 ):
      file.write("#define EEPROM_" + prefix.upper() + "_" + cmd["cmd"].upper() + str(idx) + "_BYTE" +  str(byte_count) + " (uint16_t)" + '0x{:04X}'.format(EEPROM_Count) + "\n")
    else:
       file.write("#define EEPROM_" + prefix.upper() + "_" + cmd["cmd"].upper() + "_BYTE" +  str(byte_count) + " (uint16_t)" + '0x{:04X}'.format(EEPROM_Count) + "\n\n")
    EEPROM_Count = EEPROM_Count + 1
    TotalByteCount = TotalByteCount + 1
    byte_count = byte_count + 1

def sub_write_memory_organization_2d( file, prefix, cmd, idx1, idx2 ):
  global PageCount, EEPROM_Count, TotalByteCount
  byte_count = 1
  #define EEPROM byte offset
  while byte_count <= get_eeprom_size(cmd):
    file.write("#define EEPROM_" + prefix.upper().split('_')[0].upper() + str(idx1) + "_" + prefix.upper().split('_')[1].upper() + "_" + cmd["cmd"].upper() + str(idx2) + "_BYTE" +  str(byte_count) + " (uint16_t)" + '0x{:04X}'.format(EEPROM_Count) + "\n")
    EEPROM_Count = EEPROM_Count + 1
    TotalByteCount = TotalByteCount + 1
    byte_count = byte_count + 1

def sub_write_memory_map( file, prefix, cmd, byte, depth ):
   if( depth == 2 ):
      for i in range(config["config"][cmd["count"][0]]):
         array = " {"
         for j in range(config["config"][cmd["count"][1]]):
            array = array + "EEPROM_" + prefix.upper().split('_')[0].upper() + str(i+1) + "_" + prefix.upper().split('_')[1].upper() + "_" + cmd["cmd"].upper() + str(j+1) + "_BYTE" +  str(byte)
            if( j < config["config"][cmd["count"][1]]-1):
               array = array +  ", "
         array = array + "}"
         file.write("#define EEPROM_" + prefix.upper().split('_')[0].upper() + str(i+1) + "_" + prefix.upper().split('_')[1].upper() + "_" + cmd["cmd"].upper() + "_BYTE" + str(byte) + array + "\n")
      file.write("static const uint16_t map_" + prefix.lower() + "_" + cmd["cmd"].lower() + "_byte" + str(byte) + "[" + cmd["count"][0].upper() + "]" + "[" + cmd["count"][1].upper() + "] = {" + "\n")
      for i in range(config["config"][cmd["count"][0]]):
        file.write("    EEPROM_" + prefix.upper().split('_')[0].upper() + str(i+1) + "_" + prefix.upper().split('_')[1].upper() + "_" + cmd["cmd"].upper() + "_BYTE" + str(byte) )
        if i < (config["config"][cmd["count"][0]]-1):
          file.write(",\n")
        else:
          file.write("\n")
      file.write("    };\n\n")
   else:
    file.write("static const uint16_t map_" + prefix.lower() + "_" + cmd["cmd"].lower() + "_byte" + str(byte) + "[" + cmd["count"].upper() + "] = {" + "\n")
    for i in range(config["config"][cmd["count"]]):
        file.write("    EEPROM_" + prefix.upper() + "_" + cmd["cmd"].upper() + str(i+1) + "_BYTE" + str(byte) )
        if i < (config["config"][cmd["count"]]-1):
          file.write(",\n")
        else:
          file.write("\n")
    file.write("    };\n\n")

def write_memory_organization( file, prefix, cmd, depth ):
   if( get_eeprom_size(cmd) > 0 ):
        file.write("// EEPROM Memory Map - " + prefix + " " + cmd["cmd"] + "\n")
        if( cmd["index"] ):
           if( depth == 2 ):
              for i in range(config["config"][cmd["count"][0]]):
                for j in range(config["config"][cmd["count"][1]]):
                  sub_write_memory_organization_2d( file, prefix, cmd, i+1, j+1 )
              for byte in range(get_eeprom_size(cmd)):
                sub_write_memory_map( file, prefix, cmd, byte+1, depth )
           else:
              for i in range(config["config"][cmd["count"]]):
                sub_write_memory_organization( file, prefix, cmd, i+1 )
              for byte in range(get_eeprom_size(cmd)):
                sub_write_memory_map( file, prefix, cmd, byte+1, depth )
        else:
           sub_write_memory_organization( file, prefix, cmd, 0 )

def write_variables( file, prefix, cmd, depth ):
      append = ""
      if( cmd["type"] == "string"):
          append = "[" + str(cmd["EEBytes"]).upper() + "]"
      if( cmd["index"] ):
        if( depth == 2 ):
          file.write( "static " + cmd["dataType"] + " settings_" +  prefix + "_" + cmd["cmd"].lower() +  "[" + cmd["count"][0].upper() + "]" + append + "[" + cmd["count"][1].upper() + "] = {DEFAULT_" + prefix.upper() + "_" + cmd["cmd"].upper() + "};\n" )
        else:
           file.write( "static " + cmd["dataType"] + " settings_" +  prefix + "_" + cmd["cmd"].lower() +  "[" + cmd["count"].upper() + "]" + append + " = {DEFAULT_" + prefix.upper() + "_" + cmd["cmd"].upper() + "};\n" )
      else:
        file.write( "static " + cmd["dataType"] + " settings_" + prefix + "_" + cmd["cmd"].lower() +  " = DEFAULT_" + prefix.upper() + "_" + cmd["cmd"].upper() + ";\n" )

def write_define_load_setting( file, prefix, cmd, depth ):
   if cmd["index"]:
      if( depth == 2 ):
        file.write( "static void load_" + prefix.lower() + "_" + cmd["cmd"].lower() + "(uint8_t idx_" + prefix.lower().split('_')[0] + ", uint8_t idx_" + prefix.lower().split('_')[1] + ", " + cmd["dataType"] + " *" + prefix.lower() + "_" + cmd["cmd"].lower() + "_val);\n")
      else:
        file.write( "static void load_" + prefix.lower() + "_" + cmd["cmd"].lower() + "(uint8_t idx, " + cmd["dataType"] + " *" + prefix.lower() + "_" + cmd["cmd"].lower() + "_val);\n")
   else:
      file.write( "static void load_" + prefix.lower() + "_" + cmd["cmd"].lower() + "(void);\n")

def write_load_setting( file, prefix, cmd, depth ):
   if( cmd["type"] == "string"):
      addr = ""
   else:
      addr = "&"
   if( depth == 2):
      variable1 = "idx_" + prefix.lower().split('_')[0]
      variable2 = "idx_" + prefix.lower().split('_')[1]
      file.write("    for( uint8_t " + variable1 + " = 0; " + variable1 + " < " + cmd["count"][0].upper() + "; " + variable1 +"++ )\n")
      file.write("        for( uint8_t " + variable2 + " = 0; " + variable2 + " < " + cmd["count"][1].upper() + "; " + variable2 +"++ )\n")
      file.write("            load_" + prefix.lower() + "_" + cmd["cmd"].lower() + "(idx_" + prefix.lower().split('_')[0] + ", idx_" + prefix.lower().split('_')[1] + ", &settings_" + prefix + "_" + cmd["cmd"].lower() +  "[" + variable1 + "][" + variable2 + "]);\n\n")
   else:
      variable1 = "idx"
      file.write("    for( uint8_t " + variable1 + " = 0; " + variable1 + " < " + cmd["count"].upper() + "; " + variable1 +"++ )\n")
      file.write("        load_" + prefix.lower() + "_" + cmd["cmd"].lower() + "(idx, " + addr + "settings_" + prefix + "_" + cmd["cmd"].lower() +  "[" + variable1 + "]);\n\n")

def write_normalize_loaded_setting(file, prefix, cmd, depth):
    setting = "settings_" + prefix.lower() + "_" + cmd["cmd"].lower()
    verify = "verify_" + prefix.lower() + "_" + cmd["cmd"].lower()
    default = "DEFAULT_" + prefix.upper() + "_" + cmd["cmd"].upper()

    if depth == 2:
        first, second = prefix.lower().split('_')[:2]
        file.write(f"    for (uint8_t idx_{first} = 0; idx_{first} < {cmd['count'][0].upper()}; idx_{first}++)\n")
        file.write(f"        for (uint8_t idx_{second} = 0; idx_{second} < {cmd['count'][1].upper()}; idx_{second}++)\n")
        value = f"{setting}[idx_{first}][idx_{second}]"
        indentation = "            "
    else:
        file.write(f"    for (uint8_t idx = 0; idx < {cmd['count'].upper()}; idx++)\n")
        value = f"{setting}[idx]"
        indentation = "        "

    file.write(f"{indentation}if (!{verify}({value}))\n")
    file.write(f"{indentation}{{\n")
    if cmd["type"] == "string":
        size = "EE_SIZE_" + prefix.upper() + "_" + cmd["cmd"].upper()
        file.write(f"{indentation}    memset({value}, 0, {size});\n")
        file.write(f"{indentation}    strncpy({value}, {default}, {size} - 1U);\n")
    else:
        file.write(f"{indentation}    {value} = {default};\n")
    file.write(f"{indentation}}}\n\n")
   

def write_load_source( file, prefix, cmd, depth ):
   if cmd["index"]:
      if( depth == 2 ):
        file.write( "static void load_" + prefix.lower() + "_" + cmd["cmd"].lower() + "(uint8_t idx_" + prefix.lower().split('_')[0] + ", uint8_t idx_" + prefix.lower().split('_')[1] + ", " + cmd["dataType"] + " *" + prefix.lower() + "_" + cmd["cmd"].lower() + "_val)\n")
      else:
        file.write( "static void load_" + prefix.lower() + "_" + cmd["cmd"].lower() + "(uint8_t idx, " + cmd["dataType"] + " *" + prefix.lower() + "_" + cmd["cmd"].lower() + "_val)\n")
   else:
      file.write( "static void load_" + prefix.lower() + "_" + cmd["cmd"].lower() + "(void)\n")
   file.write( "{\n" )
   file.write( "    uint8_t bytes[EE_SIZE_" + prefix.upper() + "_" + cmd["cmd"].upper() + "];\n\n" )
   # Only values that are saved in EEPROM need to be added
   if( get_eeprom_size(cmd) > 0 ):
    if( cmd["index"] ):
      if( depth == 2 ):
         index = "idx_" + prefix.lower().split('_')[0] + "][idx_" + prefix.lower().split('_')[1]
      else:
         index = "idx"
      byte_count = 1
      while byte_count <= get_eeprom_size(cmd):
        file.write("    bytes[" + str(get_eeprom_size(cmd) - byte_count) + "] = read_eeprom(map_"  + prefix.lower() + "_" + cmd["cmd"].lower() + "_byte" + str(byte_count) + "[" + index + "]);\n")
        byte_count = byte_count + 1
 
         

    file.write("\n    memcpy(" + prefix.lower() + "_" + cmd["cmd"].lower() + "_val, bytes, EE_SIZE_" + prefix.upper() + "_" + cmd["cmd"].upper() + ");\n")
   file.write( "}\n\n" )

def write_save_source( file, prefix, cmd, depth ):
    input = "(uint32_t)" + prefix + "_" + cmd["cmd"].lower()
    if( depth == 2 ):
      index = "idx_" + prefix.lower().split('_')[0] + "][idx_" + prefix.lower().split('_')[1]
    else:
      index = "idx"

    if cmd["index"]:
        if( depth == 2 ):
          file.write( "static void save_" + prefix + "_" + cmd["cmd"].lower() + "(uint8_t idx_" + prefix.lower().split('_')[0] + ", uint8_t idx_" + prefix.lower().split('_')[1] + ", " + cmd["dataType"] + " *" + prefix + "_" + cmd["cmd"].lower() + ")\n")
        else:
          file.write( "static void save_" + prefix + "_" + cmd["cmd"].lower() + "(uint8_t idx, " + cmd["dataType"] + " *" + prefix + "_" + cmd["cmd"].lower() + ")\n")
    else:
        file.write( "static void save_" + prefix + "_" + cmd["cmd"].lower() + "(" + cmd["dataType"] + " *" + prefix + "_" + cmd["cmd"].lower()  + ")\n")

    file.write( "{\n")
    
    # Only values that are saved in EEPROM need to be added
    if( get_eeprom_size(cmd) > 0 ):
        file.write( "    uint8_t bytes[EE_SIZE_" + prefix.upper() + "_" + cmd["cmd"].upper() + "];\n\n" )
        file.write("    memcpy(bytes, " + prefix.lower() + "_" + cmd["cmd"].lower() + ", EE_SIZE_" + prefix.upper() + "_" + cmd["cmd"].upper() + ");\n\n")
        if( cmd["type"] == "string" ):
            file.write("    bytes[EE_SIZE_" + prefix.upper() + "_" + cmd["cmd"].upper() + " - 1] = '\\0';\n\n")
        #file.write("    if (" + eeprom_status_check + ")\n    {\n");
        byte_count = 1
        while byte_count <= get_eeprom_size(cmd):
          file.write("    write_eeprom(map_"  + prefix.lower() + "_" + cmd["cmd"].lower() + "_byte" + str(byte_count) + "[" + index + "], bytes[" + str(get_eeprom_size(cmd) - byte_count) + "]);\n")
          byte_count = byte_count + 1

          #file.write("    }\n");

        byte_count = 1
        #define EEPROM byte offset
        while byte_count <= get_eeprom_size(cmd):
            #settings.write("    write(EEPROM_" + cmd["cmd"] + "_BYTE" + str(byte_count) + ", EE_" + cmd["cmd"] + str(byte_count) + ");\n")
            byte_count = byte_count + 1

    file.write("}\n\n")

def write_json_entry(cmd, struct, config_c, indentation, depth):
    indent = " " * indentation
    # Determine the type, optionally overridden
    type_ = cmd.get("jsonOverride", cmd["type"])

    # Choose the appropriate cJSON function
    if type_ in ("string", "list"):
        function = "cJSON_AddStringToObject"
    else:
        function = "cJSON_AddNumberToObject"

    if depth == 2:
       idx = "(i, j)"
    else:
       idx = "(i)"

    # Determine the value-getting expression
    if type_ == "list":
        get_function = f'{cmd["dataType"].lower()}_string[get_{struct}_{cmd["cmd"].lower()}{idx}]'
    elif type_ == "string":
        get_function = "str_buf"
        string_function = f'get_{struct}_{cmd["cmd"].lower()}'
        if "getFunc" in cmd:
            config_c.write(f'{indent}{cmd["getFunc"]}({string_function}{idx}, str_buf);\n')
        else:
            config_c.write(f'{indent}{string_function}(i, str_buf);\n')
    else:
        get_function = f'get_{struct}_{cmd["cmd"].lower()}{idx}'

    # Write the final cJSON call
    config_c.write(f'{indent}{function}({struct}, "{cmd["cmd"]}", {get_function});\n')

def write_json_get_entry(cmd, struct, config_c, indentation, depth):
    indent = " " * indentation
    type_ = cmd.get("jsonOverride", cmd["type"])
    datatype = cmd.get("dataType", "")
    cmd_name = cmd["cmd"].lower()
    index_args = "(i, j" if depth == 2 else "(i"

    # Determine cJSON field based on type
    if type_ in ("string", "list"):
        cjson_field = "valuestring"
        cjson_check = "cJSON_IsString"
    elif type_ == "number" and datatype == "float":
        cjson_field = "valuedouble"
        cjson_check = "cJSON_IsNumber"
    else:
        cjson_field = "valueint"
        cjson_check = "cJSON_IsNumber"

    # Determine conversion function
    if type_ == "list":
        convert_func = f"get_{struct}_{cmd_name}_from_string"
    elif type_ == "string" and cmd["dataType"] != "char": 
          convert_func = cmd.get("setFunc", f"get_{struct}_{cmd_name}_from_string")
    else:
        convert_func = ""

    # Compose function call
    value_expr = f'{convert_func}({struct}_{cmd_name}->{cjson_field})' if convert_func else f'{struct}_{cmd_name}->{cjson_field}'
    
    config_c.write(f'\n{indent}cJSON *{struct}_{cmd_name} = cJSON_GetObjectItem({struct}, "{cmd["cmd"]}");\n')
    config_c.write(f'{indent}if({cjson_check}({struct}_{cmd_name}))\n')
    config_c.write(f'{indent}    success = set_{struct}_{cmd_name}{index_args}, {value_expr}, true) && success;\n')


def process_struct( prefix, cmd, depth ):
   write_comment_block( config_h, prefix, cmd, depth )
   write_comment_block( config_c, prefix, cmd, depth )
   write_custom_struct( config_h, prefix, cmd, depth )
   write_array_string_def_extern( config_h, prefix, cmd, depth )
   write_array_string_def( config_c, prefix, cmd, depth )
   write_verify_declare( config_h, prefix, cmd, depth )
   write_load_source( config_c, prefix, cmd, depth )
   write_save_source( config_c, prefix, cmd, depth )
   write_verify_source(config_c, prefix, cmd, depth )
   write_get_source(config_c, prefix, cmd, depth)
   write_set_source(config_c, prefix, cmd, depth)
   write_get_declare( config_h, prefix, cmd, depth )
   write_set_declare( config_h, prefix, cmd, depth )
   write_string_compare_declare( config_h, prefix, cmd, depth )
   write_string_compare( config_c, prefix, cmd, depth )

for struct_entry in config["config"]["struct_list"]:
    for parent_struct, sub_structs in struct_entry.items():
        # Always process the parent struct
        for cmd in config[parent_struct]:
            write_default_define(config_c, parent_struct, cmd, 1)

        # Then process any sub-structs if they exist
        if sub_structs:
            for sub_struct in sub_structs:
                for cmd in config[sub_struct]:
                    write_default_define(config_c, f"{parent_struct}_{sub_struct}", cmd, 2)

config_c.write("\n")

for struct_entry in config["config"]["struct_list"]:
    for parent_struct, sub_structs in struct_entry.items():
        # Always process the parent struct
        for cmd in config[parent_struct]:
            write_size_define(config_c, parent_struct, cmd, 1)

        # Then process any sub-structs if they exist
        if sub_structs:
            for sub_struct in sub_structs:
                for cmd in config[sub_struct]:
                    write_size_define(config_c, f"{parent_struct}_{sub_struct}", cmd, 2)

config_c.write(f"#define EE_SIZE_SETTINGS {settings_byte_count}U\n\n")

for struct_entry in config["config"]["struct_list"]:
    for parent_struct, sub_structs in struct_entry.items():
        # Always process the parent struct
        for cmd in config[parent_struct]:
          write_memory_organization(config_c, parent_struct, cmd, 1)

        # Then process any sub-structs if they exist
        if sub_structs:
            for sub_struct in sub_structs:
                for cmd in config[sub_struct]:
                    write_memory_organization(config_c, f"{parent_struct}_{sub_struct}", cmd, 2)

if TotalByteCount != settings_byte_count:
    raise RuntimeError(
        f"EEPROM map generated {TotalByteCount} bytes; expected {settings_byte_count}"
    )

config_c.write("\n")

for struct_entry in config["config"]["struct_list"]:
    for parent_struct, sub_structs in struct_entry.items():
        # Always process the parent struct
        for cmd in config[parent_struct]:
          write_variables(config_c, parent_struct, cmd, 1)

        # Then process any sub-structs if they exist
        if sub_structs:
            for sub_struct in sub_structs:
                for cmd in config[sub_struct]:
                    write_variables(config_c, f"{parent_struct}_{sub_struct}", cmd, 2)


config_c.write("\n\n")

for struct_entry in config["config"]["struct_list"]:
    for parent_struct, sub_structs in struct_entry.items():
        # Always process the parent struct
        for cmd in config[parent_struct]:
          write_define_load_setting(config_c, parent_struct, cmd, 1)

        # Then process any sub-structs if they exist
        if sub_structs:
            for sub_struct in sub_structs:
                for cmd in config[sub_struct]:
                    write_define_load_setting(config_c, f"{parent_struct}_{sub_struct}", cmd, 2)


config_c.write("\n")

config_c.write("uint32_t options_to_json(char *buffer, uint32_t buffer_size) {\n")
config_c.write("    if ((buffer == NULL) || (buffer_size == 0U) || !cjson_shared_acquire())\n")
config_c.write("        return 0;\n\n")
config_c.write("    cJSON *root = cJSON_CreateObject();\n\n")
config_c.write("    if (!root) {\n")
config_c.write("        cjson_shared_release();\n")
config_c.write("        return 0;\n")
config_c.write("    }\n\n")
config_c.write("    cJSON *list;\n\n")

for struct_entry in config["config"]["struct_list"]:
    for parent_struct, sub_structs in struct_entry.items():
        # Always process the parent struct
        for cmd in config[parent_struct]:
                if cmd["type"] == "list":
                  array_name = f'{cmd["dataType"].lower()}_string'
                  json_entry = f'{cmd["dataType"].lower()}'
                  limit = f'{cmd["dataType"].upper()}_RESERVED'
                  config_c.write(f"    // Populate {json_entry} option list\n")
                  config_c.write(f"    list = cJSON_CreateStringArray({array_name}, {limit});\n")
                  config_c.write(f"    cJSON_AddItemToObject(root, \"{json_entry}\", list);\n\n")


        # Then process any sub-structs if they exist
        if sub_structs:
            for sub_struct in sub_structs:
                print(f"Parent struct: {parent_struct}, Sub-struct: {sub_struct}")
                for cmd in config[sub_struct]:
                  if cmd["type"] == "list":
                    array_name = f'{cmd["dataType"].lower()}_string'
                    json_entry = f'{cmd["dataType"].lower()}'
                    limit = f'{cmd["dataType"].upper()}_RESERVED'
                    config_c.write(f"    // Populate {json_entry} option list\n")
                    config_c.write(f"    list = cJSON_CreateStringArray({array_name}, {limit});\n")
                    config_c.write(f"    cJSON_AddItemToObject(root, \"{json_entry}\", list);\n\n")

config_c.write("    uint32_t actual_len = 0;\n")
config_c.write("\n    if (cJSON_PrintPreallocated(root, buffer, (int)buffer_size, false)) {\n")
config_c.write("        actual_len = (uint32_t)strlen(buffer);\n")
config_c.write("    }\n\n")
config_c.write("    cJSON_Delete(root);\n")
config_c.write("    cjson_shared_release();\n")
config_c.write("    return actual_len; // 0 means failure\n")
config_c.write("}\n\n")

config_c.write("uint32_t config_to_json(char *buffer, uint32_t buffer_size) {\n")
config_c.write("    if ((buffer == NULL) || (buffer_size == 0U) || !cjson_shared_acquire())\n")
config_c.write("        return 0;\n\n")
config_c.write("    cJSON *root = cJSON_CreateObject();\n\n")
config_c.write("    if (!root) {\n")
config_c.write("        cjson_shared_release();\n")
config_c.write("        return 0;\n")
config_c.write("    }\n\n")
config_c.write("    char str_buf[1024];\n")

for struct_entry in config["config"]["struct_list"]:
    for parent_struct, sub_structs in struct_entry.items():
        # Always process the parent struct
        config_c.write(f"\n    // Serialize {parent_struct}\n")
        config_c.write(f"    cJSON *{parent_struct}s = cJSON_AddArrayToObject(root, \"{parent_struct}\");\n")
        config_c.write(f"    for(int i = 0; i < MAX_{parent_struct.upper()}S; i++) {{\n")
        config_c.write(f"        cJSON *{parent_struct} = cJSON_CreateObject();\n")
        for cmd in config[parent_struct]:
          write_json_entry(cmd, parent_struct, config_c, 8, 1)

        if sub_structs:  # Parent has sub-items
            for sub_struct in sub_structs:
                config_c.write(f"\n        // Serialize {sub_struct} within {parent_struct}\n")
                config_c.write(f"        cJSON *{parent_struct}_{sub_struct}s = cJSON_AddArrayToObject({parent_struct}, \"{sub_struct}\");\n")
                config_c.write(f"        for(int j = 0; j < MAX_{sub_struct.upper()}S_PER_{parent_struct.upper()}; j++) {{\n")
                config_c.write(f"            cJSON *{parent_struct}_{sub_struct} = cJSON_CreateObject();\n")
                for cmd in config[sub_struct]:
                  write_json_entry(cmd, (f"{parent_struct}_{sub_struct}"), config_c, 12, 2)
                config_c.write(f"            cJSON_AddItemToArray({parent_struct}_{sub_struct}s, {parent_struct}_{sub_struct});\n")
                config_c.write(f"        }}\n")

        config_c.write(f"        cJSON_AddItemToArray({parent_struct}s, {parent_struct});\n")
        config_c.write(f"    }}\n")

config_c.write("\n")
config_c.write("    uint32_t actual_len = 0;\n")
config_c.write("\n    if (cJSON_PrintPreallocated(root, buffer, (int)buffer_size, false)) {\n")
config_c.write("        actual_len = (uint32_t)strlen(buffer);\n")
config_c.write("    }\n\n")
config_c.write("    cJSON_Delete(root);\n")
config_c.write("    cjson_shared_release();\n")
config_c.write("    return actual_len; // 0 means failure\n")
config_c.write("}\n\n")

config_c.write("bool json_to_config(const char *json_str) {\n")
config_c.write("    if ((json_str == NULL) || !cjson_shared_acquire())\n")
config_c.write("        return false;\n\n")
config_c.write("    cJSON *root = cJSON_Parse(json_str);\n\n")
config_c.write("    if (!root) {\n")
config_c.write("        cjson_shared_release();\n")
config_c.write("        return false;\n")
config_c.write("    }\n")
config_c.write("\n    bool success = true;\n")

for struct_entry in config["config"]["struct_list"]:
    for parent_struct, sub_structs in struct_entry.items():
        # Always process the parent struct
        config_c.write(f"\n    // Get {parent_struct}\n")
        config_c.write(f"    cJSON *{parent_struct}s = cJSON_GetObjectItem(root, \"{parent_struct}\");\n")
        config_c.write(f"    if({parent_struct}s && cJSON_IsArray({parent_struct}s)) {{\n")
        config_c.write(f"        for(int i = 0; (i < MAX_{parent_struct.upper()}S) && (i < cJSON_GetArraySize({parent_struct}s)); i++) {{\n")
        config_c.write(f"            cJSON *{parent_struct} = cJSON_GetArrayItem({parent_struct}s, i);\n")
        for cmd in config[parent_struct]:
          write_json_get_entry(cmd, parent_struct, config_c, 12, 1)

        if sub_structs:  # Parent has sub-items
            for sub_struct in sub_structs:
                config_c.write(f"\n            // Get {sub_struct} within {parent_struct}\n")
                config_c.write(f"            cJSON *{parent_struct}_{sub_struct}s = cJSON_GetObjectItem({parent_struct}, \"{sub_struct}\");\n")
                config_c.write(f"            if({parent_struct}_{sub_struct}s && cJSON_IsArray({parent_struct}_{sub_struct}s)) {{\n")
                config_c.write(f"                for(int j = 0; j < MAX_{sub_struct.upper()}S_PER_{parent_struct.upper()}; j++) {{\n")
                config_c.write(f"                    cJSON *{parent_struct}_{sub_struct} = cJSON_GetArrayItem({parent_struct}_{sub_struct}s, j);\n")
                config_c.write(f"                    if({parent_struct}_{sub_struct}) {{\n")
                for cmd in config[sub_struct]:
                  write_json_get_entry(cmd, (f"{parent_struct}_{sub_struct}"), config_c, 24, 2)
                config_c.write(f"                    }}\n")
                config_c.write(f"                }}\n")
                config_c.write(f"            }}\n")

        config_c.write(f"        }}\n")
        config_c.write(f"    }}\n")

config_c.write("\n    // Print into user buffer\n")
config_c.write("    cJSON_Delete(root);\n")
config_c.write("    cjson_shared_release();\n")
config_c.write("    return success;\n")
config_c.write("}\n\n")


config_c.write("static uint8_t cached_settings[EE_SIZE_SETTINGS];\n\n")

config_c.write("static settings_write *write;\n")
config_c.write("static settings_read *read;\n\n")
config_c.write("void settings_setWriteHandler(settings_write *writeHandler) { write = writeHandler; }\n")
config_c.write("void settings_setReadHandler(settings_read *readHandler) { read = readHandler; }\n\n")

config_c.write("uint8_t read_eeprom(uint16_t bAdd)\n")
config_c.write("{\n")
config_c.write("\tif ((read == NULL) || (bAdd >= EE_SIZE_SETTINGS))\n")
config_c.write("\t\treturn 0xFF;\n\n")
config_c.write("	uint8_t byte = 0xFF;\n")
config_c.write("	byte = read(bAdd); // Read from the EEPROM\n")
config_c.write("	cached_settings[bAdd] = byte; // cache the data\n")
config_c.write("	return byte;\n")
config_c.write("}\n\n")

config_c.write("void write_eeprom(uint16_t bAdd, uint8_t bData)\n")
config_c.write("{\n")
config_c.write("\tif ((write == NULL) || (bAdd >= EE_SIZE_SETTINGS))\n")
config_c.write("\t\treturn;\n\n")
config_c.write("	write(bAdd, bData); // Write to the EEPROM\n")
config_c.write("	cached_settings[bAdd] = bData; // cache the data\n")
config_c.write("}\n\n")

config_c.write("uint8_t get_eeprom_byte(uint16_t bAdd)\n")
config_c.write("{\n")
config_c.write("\tif (bAdd >= EE_SIZE_SETTINGS)\n")
config_c.write("\t\treturn 0xFF;\n\n")
config_c.write("	return cached_settings[bAdd];\n")
config_c.write("}\n\n")

config_c.write("void settings_erase_eeprom(void)\n")
config_c.write("{\n")
config_c.write("\tfor (uint16_t address = 0; address < EE_SIZE_SETTINGS; address++)\n")
config_c.write("\t{\n")
config_c.write("\t\twrite_eeprom(address, 0xFF);\n")
config_c.write("\t}\n")
config_c.write("}\n\n")

config_h.write("\n\nvoid load_settings(void);\n")
config_h.write("void settings_erase_eeprom(void);\n")
config_h.write("void write_eeprom(uint16_t bAdd, uint8_t bData);\n")
config_h.write("uint8_t get_eeprom_byte(uint16_t bAdd);\n")
config_h.write("uint32_t options_to_json(char *buffer, uint32_t buffer_size);\n")
config_h.write("uint32_t config_to_json(char *buffer, uint32_t buffer_size);\n")
config_h.write("bool json_to_config(const char *json_str)\n;")

config_c.write("void load_settings(void)\n{\n")
for struct_entry in config["config"]["struct_list"]:
    for parent_struct, sub_structs in struct_entry.items():
        # Always process the parent struct
        for cmd in config[parent_struct]:
            write_load_setting(config_c, parent_struct, cmd, 1)

        if sub_structs:  # Parent has sub-items
            for sub_struct in sub_structs:
                print(f"Parent struct: {parent_struct}, Sub-struct: {sub_struct}")
                for cmd in config[sub_struct]:
                    write_load_setting(config_c, f"{parent_struct}_{sub_struct}", cmd, 2)

config_c.write("    // Normalize every value immediately after reading raw EEPROM bytes.\n")
for struct_entry in config["config"]["struct_list"]:
    for parent_struct, sub_structs in struct_entry.items():
        for cmd in config[parent_struct]:
            write_normalize_loaded_setting(config_c, parent_struct, cmd, 1)

        for sub_struct in sub_structs:
            for cmd in config[sub_struct]:
                write_normalize_loaded_setting(
                    config_c, f"{parent_struct}_{sub_struct}", cmd, 2
                )

config_c.write("}\n")

config_c.write("\n\n")

for struct_entry in config["config"]["struct_list"]:
    for parent_struct, sub_structs in struct_entry.items():
        # Always process the parent struct
        for cmd in config[parent_struct]:
            process_struct(parent_struct, cmd, 1)

        # Then process any sub-structs if they exist
        if sub_structs:
            for sub_struct in sub_structs:
                print(f"Parent struct: {parent_struct}, Sub-struct: {sub_struct}")
                for cmd in config[sub_struct]:
                    process_struct(f"{parent_struct}_{sub_struct}", cmd, 2)


config_h.write("\n#ifdef __cplusplus\n")
config_h.write("}\n")
config_h.write("#endif\n\n")
config_h.write("#endif /* KE_CONFIG_H */")

(module_dir / "src" / "ke_config.c").write_text(config_c.getvalue(), newline="\n")
(module_dir / "inc" / "ke_config.h").write_text(config_h.getvalue(), newline="\n")

write_stats_readme()

print(
    f"Usage: {TotalByteCount}B of {eeprom_capacity_bytes}B "
    f"({eeprom_capacity_kbit}kbit) "
    f"({TotalByteCount / eeprom_capacity_bytes * 100:.2f}%)"
)
print(f"Estimated load time at {i2c_clock_hz / 1000:g}kHz: {load_time_seconds * 1000:.1f}ms")
print(
    f"Estimated mass erase time: {erase_typical_seconds:.2f}s typical, "
    f"{erase_max_seconds:.2f}s maximum"
)
