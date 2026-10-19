add_library(driver_wiimotion SHARED src/driver.cpp)
target_compile_features(driver_wiimotion PRIVATE cxx_std_17)
target_include_directories(driver_wiimotion PRIVATE include "${OPENVR_ROOT}/headers")
target_compile_definitions(driver_wiimotion PRIVATE WIN32_LEAN_AND_MEAN NOMINMAX)
set_target_properties(driver_wiimotion PROPERTIES OUTPUT_NAME "driver_wiimotion" PREFIX "")
set_target_properties(driver_wiimotion PROPERTIES
  RUNTIME_OUTPUT_DIRECTORY_RELEASE "${CMAKE_BINARY_DIR}/package/driver/wiimotionsteamvr/bin/win64"
  LIBRARY_OUTPUT_DIRECTORY_RELEASE "${CMAKE_BINARY_DIR}/package/driver/wiimotionsteamvr/bin/win64")
add_custom_command(TARGET driver_wiimotion POST_BUILD
  COMMAND ${CMAKE_COMMAND} -E copy_directory "${CMAKE_SOURCE_DIR}/driver/resources" "${CMAKE_BINARY_DIR}/package/driver/wiimotionsteamvr/resources"
  COMMAND ${CMAKE_COMMAND} -E copy "${CMAKE_SOURCE_DIR}/driver/driver.vrdrivermanifest" "${CMAKE_BINARY_DIR}/package/driver/wiimotionsteamvr/driver.vrdrivermanifest"
  COMMAND ${CMAKE_COMMAND} -E make_directory "${CMAKE_BINARY_DIR}/package/driver/wiimotionsteamvr/config"
  COMMAND ${CMAKE_COMMAND} -E copy "${CMAKE_SOURCE_DIR}/config/config.json" "${CMAKE_BINARY_DIR}/package/driver/wiimotionsteamvr/config/config.json")
