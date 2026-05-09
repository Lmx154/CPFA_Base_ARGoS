#ifndef DECENTRALIZED_PHEROMONE_H
#define DECENTRALIZED_PHEROMONE_H

#include <argos3/core/utility/math/vector2.h>
#include <cstddef>
#include <string>
#include <vector>

class DecentralizedPheromone {
public:
    DecentralizedPheromone();
    DecentralizedPheromone(const std::string& new_id,
                           const std::string& new_origin_robot_id,
                           const argos::CVector2& new_location,
                           const std::vector<argos::CVector2>& new_trail,
                           argos::Real current_time,
                           argos::Real new_decay_rate,
                           size_t new_resource_density);

    static std::string MakeId(const std::string& origin_robot_id,
                              size_t creation_tick,
                              const argos::CVector2& location);

    void Update(argos::Real current_time);
    bool IsActive() const;
    argos::Real SelectionWeight() const;

    std::string id;
    std::string origin_robot_id;
    argos::CVector2 location;
    std::vector<argos::CVector2> trail;
    argos::Real created_time;
    argos::Real last_updated_time;
    argos::Real decay_rate;
    argos::Real weight;
    argos::Real threshold;
    size_t resource_density;
    size_t hop_count;
};

#endif
