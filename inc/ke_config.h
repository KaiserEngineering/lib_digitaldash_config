/**
 ******************************************************************************
 *
 * Copyright (c) 2025 KaiserEngineering, LLC
 * Author Matthew Kaiser
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy
 * of this software and associated documentation files (the "Software"), to deal
 * in the Software without restriction, including without limitation the rights
 * to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
 * copies of the Software, and to permit persons to whom the Software is
 * furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in all
 * copies or substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 * IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 * FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
 * LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
 * OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
 * SOFTWARE.
 *
 ******************************************************************************
 */

#ifndef KE_CONFIG_H
#define KE_CONFIG_H

#ifdef __cplusplus
extern "C"
{
#endif

#include <stdbool.h>
#include <string.h>
#include <stdlib.h>
#include "cJSON.h"
#include "lib_pid.h"

typedef void(settings_write)(uint16_t bAdd, uint8_t bData);
typedef uint8_t(settings_read)(uint16_t bAdd);

void settings_setWriteHandler(settings_write *writeHandler);
void settings_setReadHandler(settings_read *readHandler);

#define MAX_GAUGES_PER_VIEW 3
#define MAX_ALERTS 5
#define ALERT_MESSAGE_LEN 64
#define MAX_VIEWS 3
#define MAX_DYNAMICS 3
#define MAX_GENERALS 1

void load_settings(void);
void write_eeprom(uint16_t bAdd, uint8_t bData);
uint8_t get_eeprom_byte(uint16_t bAdd);
uint32_t options_to_json(char *buffer, uint32_t buffer_size);
uint32_t config_to_json(char *buffer, uint32_t buffer_size);
bool json_to_config(const char *json_str)
;

/********************************************************************************
*                                  View enable                                  
*
* @param idx_view    index of the view
* @param enable    Enable or disable view by index
* @param save    Set true to save to the EEPROM, otherwise value is non-volatile
*
********************************************************************************/
typedef enum
{
    VIEW_STATE_DISABLED,
    VIEW_STATE_ENABLED,
    VIEW_STATE_RESERVED
} VIEW_STATE;

extern const char *view_state_string[];
bool verify_view_enable(VIEW_STATE enable);
VIEW_STATE get_view_enable(uint8_t idx_view);
bool set_view_enable(uint8_t idx_view, VIEW_STATE enable, bool save);
VIEW_STATE get_view_enable_from_string(const char *str);


/********************************************************************************
*                                Number of gauges                               
*
* @param idx_view    index of the view
* @param num_gauges    Define the number of gauges for view by index
* @param save    Set true to save to the EEPROM, otherwise value is non-volatile
*
********************************************************************************/
bool verify_view_num_gauges(uint8_t num_gauges);
uint8_t get_view_num_gauges(uint8_t idx_view);
bool set_view_num_gauges(uint8_t idx_view, uint8_t num_gauges, bool save);


/********************************************************************************
*                                   Background                                  
*
* @param idx_view    index of the view
* @param background    Set the background color or image of a view by index
* @param save    Set true to save to the EEPROM, otherwise value is non-volatile
*
********************************************************************************/
typedef enum
{
    VIEW_BACKGROUND_USER1,
    VIEW_BACKGROUND_USER2,
    VIEW_BACKGROUND_USER3,
    VIEW_BACKGROUND_USER4,
    VIEW_BACKGROUND_USER5,
    VIEW_BACKGROUND_USER6,
    VIEW_BACKGROUND_USER7,
    VIEW_BACKGROUND_USER8,
    VIEW_BACKGROUND_USER9,
    VIEW_BACKGROUND_USER10,
    VIEW_BACKGROUND_USER11,
    VIEW_BACKGROUND_USER12,
    VIEW_BACKGROUND_USER13,
    VIEW_BACKGROUND_USER14,
    VIEW_BACKGROUND_USER15,
    VIEW_BACKGROUND_RESERVED
} VIEW_BACKGROUND;

extern const char *view_background_string[];
bool verify_view_background(VIEW_BACKGROUND background);
VIEW_BACKGROUND get_view_background(uint8_t idx_view);
bool set_view_background(uint8_t idx_view, VIEW_BACKGROUND background, bool save);
VIEW_BACKGROUND get_view_background_from_string(const char *str);


/********************************************************************************
*                          Theme assigned to the gauge                          
*
* @param idx_view    index of the view
* @param idx_gauge    index of the gauge
* @param theme    Set the gauge theme by view and gauge index
* @param save    Set true to save to the EEPROM, otherwise value is non-volatile
*
********************************************************************************/
typedef enum
{
    GAUGE_THEME_STOCK_ST,
    GAUGE_THEME_STOCK_RS,
    GAUGE_THEME_GRUMPY_CAT,
    GAUGE_THEME_LINEAR,
    GAUGE_THEME_RADIAL,
    GAUGE_THEME_DIGITAL,
    GAUGE_THEME_RESERVED
} GAUGE_THEME;

extern const char *gauge_theme_string[];
bool verify_view_gauge_theme(GAUGE_THEME theme);
GAUGE_THEME get_view_gauge_theme(uint8_t idx_view, uint8_t idx_gauge);
bool set_view_gauge_theme(uint8_t idx_view, uint8_t idx_gauge,  GAUGE_THEME theme, bool save);
GAUGE_THEME get_view_gauge_theme_from_string(const char *str);


/********************************************************************************
*                           PID assigned to the gauge                           
*
* @param idx_view    index of the view
* @param idx_gauge    index of the gauge
* @param pid    Set the gauge PID by view and gauge index
* @param save    Set true to save to the EEPROM, otherwise value is non-volatile
*
********************************************************************************/
bool verify_view_gauge_pid(uint32_t pid);
uint32_t get_view_gauge_pid(uint8_t idx_view, uint8_t idx_gauge);
bool set_view_gauge_pid(uint8_t idx_view, uint8_t idx_gauge,  uint32_t pid, bool save);


/********************************************************************************
*                        PID units assigned to the gauge                        
*
* @param idx_view    index of the view
* @param idx_gauge    index of the gauge
* @param units    Set the PID units by view and gauge index
* @param save    Set true to save to the EEPROM, otherwise value is non-volatile
*
********************************************************************************/
bool verify_view_gauge_units(PID_UNITS units);
PID_UNITS get_view_gauge_units(uint8_t idx_view, uint8_t idx_gauge);
bool set_view_gauge_units(uint8_t idx_view, uint8_t idx_gauge,  PID_UNITS units, bool save);


/********************************************************************************
*                                  Alert enable                                 
*
* @param idx_alert    index of the alert
* @param enable    Enable or disable view by index
* @param save    Set true to save to the EEPROM, otherwise value is non-volatile
*
********************************************************************************/
typedef enum
{
    ALERT_STATE_DISABLED,
    ALERT_STATE_ENABLED,
    ALERT_STATE_RESERVED
} ALERT_STATE;

extern const char *alert_state_string[];
bool verify_alert_enable(ALERT_STATE enable);
ALERT_STATE get_alert_enable(uint8_t idx_alert);
bool set_alert_enable(uint8_t idx_alert, ALERT_STATE enable, bool save);
ALERT_STATE get_alert_enable_from_string(const char *str);


/********************************************************************************
*                           PID assigned to the alert                           
*
* @param idx_alert    index of the alert
* @param pid    Set the PID by alert index
* @param save    Set true to save to the EEPROM, otherwise value is non-volatile
*
********************************************************************************/
bool verify_alert_pid(uint32_t pid);
uint32_t get_alert_pid(uint8_t idx_alert);
bool set_alert_pid(uint8_t idx_alert, uint32_t pid, bool save);


/********************************************************************************
*                        PID units assigned to the alert                        
*
* @param idx_alert    index of the alert
* @param units    Set the PID units by alert index
* @param save    Set true to save to the EEPROM, otherwise value is non-volatile
*
********************************************************************************/
bool verify_alert_units(PID_UNITS units);
PID_UNITS get_alert_units(uint8_t idx_alert);
bool set_alert_units(uint8_t idx_alert, PID_UNITS units, bool save);


/********************************************************************************
*                                 Alert message                                 
*
* @param idx_alert    index of the alert
* @param message    Set the message that appears when alert occurs
* @param save    Set true to save to the EEPROM, otherwise value is non-volatile
*
********************************************************************************/
bool verify_alert_message(char* message);
void get_alert_message(uint8_t idx, char* alert_message);
bool set_alert_message(uint8_t idx_alert, char* message, bool save);


/********************************************************************************
*                                Comparison type                                
*
* @param idx_alert    index of the alert
* @param compare    Configure the comparison used for the realtime value and alert threshold
* @param save    Set true to save to the EEPROM, otherwise value is non-volatile
*
********************************************************************************/
typedef enum
{
    ALERT_COMPARISON_LESS_THAN,
    ALERT_COMPARISON_LESS_THAN_OR_EQUAL_TO,
    ALERT_COMPARISON_GREATER_THAN,
    ALERT_COMPARISON_GREATER_THAN_OR_EQUAL_TO,
    ALERT_COMPARISON_EQUAL,
    ALERT_COMPARISON_NOT_EQUAL,
    ALERT_COMPARISON_RESERVED
} ALERT_COMPARISON;

extern const char *alert_comparison_string[];
bool verify_alert_compare(ALERT_COMPARISON compare);
ALERT_COMPARISON get_alert_compare(uint8_t idx_alert);
bool set_alert_compare(uint8_t idx_alert, ALERT_COMPARISON compare, bool save);
ALERT_COMPARISON get_alert_compare_from_string(const char *str);


/********************************************************************************
*                                Alert threshold                                
*
* @param idx_alert    index of the alert
* @param threshold    Comparison value of the alert
* @param save    Set true to save to the EEPROM, otherwise value is non-volatile
*
********************************************************************************/
bool verify_alert_threshold(float threshold);
float get_alert_threshold(uint8_t idx_alert);
bool set_alert_threshold(uint8_t idx_alert, float threshold, bool save);


/********************************************************************************
*                                 Dynamic enable                                
*
* @param idx_dynamic    index of the dynamic
* @param enable    Enable or disable view by index
* @param save    Set true to save to the EEPROM, otherwise value is non-volatile
*
********************************************************************************/
typedef enum
{
    DYNAMIC_STATE_DISABLED,
    DYNAMIC_STATE_ENABLED,
    DYNAMIC_STATE_RESERVED
} DYNAMIC_STATE;

extern const char *dynamic_state_string[];
bool verify_dynamic_enable(DYNAMIC_STATE enable);
DYNAMIC_STATE get_dynamic_enable(uint8_t idx_dynamic);
bool set_dynamic_enable(uint8_t idx_dynamic, DYNAMIC_STATE enable, bool save);
DYNAMIC_STATE get_dynamic_enable_from_string(const char *str);


/********************************************************************************
*                                    Priority                                   
*
* @param idx_dynamic    index of the dynamic
* @param priority    Priority of the dynamic gauges, if both gauges comparisons are met then highest priority wins
* @param save    Set true to save to the EEPROM, otherwise value is non-volatile
*
********************************************************************************/
typedef enum
{
    DYNAMIC_PRIORITY_LOW,
    DYNAMIC_PRIORITY_MEDIUM,
    DYNAMIC_PRIORITY_HIGH,
    DYNAMIC_PRIORITY_RESERVED
} DYNAMIC_PRIORITY;

extern const char *dynamic_priority_string[];
bool verify_dynamic_priority(DYNAMIC_PRIORITY priority);
DYNAMIC_PRIORITY get_dynamic_priority(uint8_t idx_dynamic);
bool set_dynamic_priority(uint8_t idx_dynamic, DYNAMIC_PRIORITY priority, bool save);
DYNAMIC_PRIORITY get_dynamic_priority_from_string(const char *str);


/********************************************************************************
*                                Comparison type                                
*
* @param idx_dynamic    index of the dynamic
* @param compare    Configure the comparison used for the realtime value and alert threshold
* @param save    Set true to save to the EEPROM, otherwise value is non-volatile
*
********************************************************************************/
typedef enum
{
    DYNAMIC_COMPARISON_LESS_THAN,
    DYNAMIC_COMPARISON_LESS_THAN_OR_EQUAL_TO,
    DYNAMIC_COMPARISON_GREATER_THAN,
    DYNAMIC_COMPARISON_GREATER_THAN_OR_EQUAL_TO,
    DYNAMIC_COMPARISON_EQUAL,
    DYNAMIC_COMPARISON_NOT_EQUAL,
    DYNAMIC_COMPARISON_RESERVED
} DYNAMIC_COMPARISON;

extern const char *dynamic_comparison_string[];
bool verify_dynamic_compare(DYNAMIC_COMPARISON compare);
DYNAMIC_COMPARISON get_dynamic_compare(uint8_t idx_dynamic);
bool set_dynamic_compare(uint8_t idx_dynamic, DYNAMIC_COMPARISON compare, bool save);
DYNAMIC_COMPARISON get_dynamic_compare_from_string(const char *str);


/********************************************************************************
*                            Dynamic gauge threshold                            
*
* @param idx_dynamic    index of the dynamic
* @param threshold    Comparison value of the dynamic gauge
* @param save    Set true to save to the EEPROM, otherwise value is non-volatile
*
********************************************************************************/
bool verify_dynamic_threshold(float threshold);
float get_dynamic_threshold(uint8_t idx_dynamic);
bool set_dynamic_threshold(uint8_t idx_dynamic, float threshold, bool save);


/********************************************************************************
*                                   View index                                  
*
* @param idx_dynamic    index of the dynamic
* @param view_index    Set which view should be enabled if the dynamic event is true
* @param save    Set true to save to the EEPROM, otherwise value is non-volatile
*
********************************************************************************/
bool verify_dynamic_view_index(uint8_t view_index);
uint8_t get_dynamic_view_index(uint8_t idx_dynamic);
bool set_dynamic_view_index(uint8_t idx_dynamic, uint8_t view_index, bool save);


/********************************************************************************
*                       PID assigned to the dynamic gauge                       
*
* @param idx_dynamic    index of the dynamic
* @param pid    Set the dynamic PID by dynamic index
* @param save    Set true to save to the EEPROM, otherwise value is non-volatile
*
********************************************************************************/
bool verify_dynamic_pid(uint32_t pid);
uint32_t get_dynamic_pid(uint8_t idx_dynamic);
bool set_dynamic_pid(uint8_t idx_dynamic, uint32_t pid, bool save);


/********************************************************************************
*                       PID units assigned to the dynamic                       
*
* @param idx_dynamic    index of the dynamic
* @param units    Set the PID units by dynamic index
* @param save    Set true to save to the EEPROM, otherwise value is non-volatile
*
********************************************************************************/
bool verify_dynamic_units(PID_UNITS units);
PID_UNITS get_dynamic_units(uint8_t idx_dynamic);
bool set_dynamic_units(uint8_t idx_dynamic, PID_UNITS units, bool save);


/********************************************************************************
*                                 EEPROM Version                                
*
* @param idx_general    index of the general
* @param EE_Version    EEPROM Version
* @param save    Set true to save to the EEPROM, otherwise value is non-volatile
*
********************************************************************************/
bool verify_general_ee_version(uint8_t ee_version);
uint8_t get_general_ee_version(uint8_t idx_general);
bool set_general_ee_version(uint8_t idx_general, uint8_t ee_version, bool save);

#ifdef __cplusplus
}
#endif

#endif /* KE_CONFIG_H */