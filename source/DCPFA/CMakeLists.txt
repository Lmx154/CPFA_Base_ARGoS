
###############################################
# define shared object files
###############################################

add_library(DCPFA_loop_functions SHARED DCPFA_loop_functions.h
                                       DCPFA_loop_functions.cpp
                                       DCPFA_qt_user_functions.h
                                       DCPFA_qt_user_functions.cpp)

add_library(DCPFA_controller     SHARED DCPFA_controller.h
                                       DCPFA_controller.cpp
                                       DecentralizedPheromone.h
                                       DecentralizedPheromone.cpp
                                       RobotPheromoneMemory.h
                                       RobotPheromoneMemory.cpp
                                       DCPFA_loop_functions.h
                                       DCPFA_loop_functions.cpp)

###############################################
# link shared object files to dependencies
###############################################

target_link_libraries(DCPFA_controller
                      BaseController
                      Pheromone
                      Nest)

target_link_libraries(DCPFA_loop_functions
                      DCPFA_controller
                      argos3core_simulator
                      argos3plugin_simulator_entities
                      argos3plugin_simulator_footbot
                      argos3plugin_simulator_genericrobot
                      argos3plugin_simulator_qtopengl
                      ${ARGOS_QTOPENGL_LIBRARIES})
