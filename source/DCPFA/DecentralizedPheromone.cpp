#include "DecentralizedPheromone.h"

#include <algorithm>
#include <cmath>
#include <sstream>

DecentralizedPheromone::DecentralizedPheromone() :
    created_time(0.0),
    last_updated_time(0.0),
    decay_rate(0.0),
    weight(0.0),
    threshold(0.001),
    resource_density(0),
    hop_count(0)
{}

DecentralizedPheromone::DecentralizedPheromone(
    const std::string& new_id,
    const std::string& new_origin_robot_id,
    const argos::CVector2& new_location,
    const std::vector<argos::CVector2>& new_trail,
    argos::Real current_time,
    argos::Real new_decay_rate,
    size_t new_resource_density) :
    id(new_id),
    origin_robot_id(new_origin_robot_id),
    location(new_location),
    trail(new_trail),
    created_time(current_time),
    last_updated_time(current_time),
    decay_rate(new_decay_rate),
    weight(1.0),
    threshold(0.001),
    resource_density(new_resource_density),
    hop_count(0)
{}

std::string DecentralizedPheromone::MakeId(const std::string& origin_robot_id,
                                           size_t creation_tick,
                                           const argos::CVector2& location) {
    const long quantized_x = static_cast<long>(std::floor(location.GetX() * 100.0));
    const long quantized_y = static_cast<long>(std::floor(location.GetY() * 100.0));

    std::ostringstream id_builder;
    id_builder << origin_robot_id << '_'
               << creation_tick << '_'
               << quantized_x << '_'
               << quantized_y;
    return id_builder.str();
}

void DecentralizedPheromone::Update(argos::Real current_time) {
    if(current_time <= last_updated_time) {
        return;
    }

    weight *= std::exp(-decay_rate * (current_time - last_updated_time));
    last_updated_time = current_time;
}

bool DecentralizedPheromone::IsActive() const {
    return weight > threshold;
}

argos::Real DecentralizedPheromone::SelectionWeight() const {
    return weight * std::max<size_t>(1, resource_density);
}
