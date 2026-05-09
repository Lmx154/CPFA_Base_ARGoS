#include "RobotPheromoneMemory.h"

#include <algorithm>

RobotPheromoneMemory::RobotPheromoneMemory(size_t max_pheromones) :
    MaxPheromones(max_pheromones)
{}

void RobotPheromoneMemory::Clear() {
    Pheromones.clear();
}

void RobotPheromoneMemory::SetMaxSize(size_t max_pheromones) {
    MaxPheromones = max_pheromones;
    EnforceCapacity();
}

void RobotPheromoneMemory::AddLocalPheromone(
    const std::string& origin_robot_id,
    size_t creation_tick,
    const argos::CVector2& location,
    const std::vector<argos::CVector2>& trail,
    argos::Real current_time,
    argos::Real decay_rate,
    size_t resource_density) {
    const std::string id = DecentralizedPheromone::MakeId(origin_robot_id, creation_tick, location);
    ReceivePheromone(DecentralizedPheromone(id,
                                            origin_robot_id,
                                            location,
                                            trail,
                                            current_time,
                                            decay_rate,
                                            resource_density));
}

bool RobotPheromoneMemory::ReceivePheromone(const DecentralizedPheromone& incoming) {
    if(!incoming.IsActive()) {
        return false;
    }

    for(size_t i = 0; i < Pheromones.size(); ++i) {
        if(Pheromones[i].id == incoming.id) {
            if(incoming.weight > Pheromones[i].weight ||
               incoming.last_updated_time > Pheromones[i].last_updated_time) {
                Pheromones[i] = incoming;
            }
            return false;
        }
    }

    Pheromones.push_back(incoming);
    EnforceCapacity();
    return true;
}

size_t RobotPheromoneMemory::ReceivePheromones(const std::vector<DecentralizedPheromone>& incoming) {
    size_t accepted = 0;
    for(size_t i = 0; i < incoming.size(); ++i) {
        if(ReceivePheromone(incoming[i])) {
            ++accepted;
        }
    }
    return accepted;
}

std::vector<DecentralizedPheromone> RobotPheromoneMemory::ExportActivePheromones() const {
    std::vector<DecentralizedPheromone> active;
    for(size_t i = 0; i < Pheromones.size(); ++i) {
        if(Pheromones[i].IsActive()) {
            active.push_back(Pheromones[i]);
        }
    }
    return active;
}

void RobotPheromoneMemory::DecayAndPrune(argos::Real current_time) {
    for(size_t i = 0; i < Pheromones.size(); ++i) {
        Pheromones[i].Update(current_time);
    }

    Pheromones.erase(
        std::remove_if(Pheromones.begin(),
                       Pheromones.end(),
                       [](const DecentralizedPheromone& pheromone) {
                           return !pheromone.IsActive();
                       }),
        Pheromones.end());
    EnforceCapacity();
}

bool RobotPheromoneMemory::SelectTarget(argos::CRandom::CRNG* rng,
                                        argos::CVector2& target_out,
                                        std::vector<argos::CVector2>* trail_out) const {
    argos::Real total_weight = 0.0;

    for(size_t i = 0; i < Pheromones.size(); ++i) {
        if(Pheromones[i].IsActive()) {
            total_weight += Pheromones[i].SelectionWeight();
        }
    }

    if(total_weight <= 0.0) {
        return false;
    }

    argos::Real random_weight = rng->Uniform(argos::CRange<argos::Real>(0.0, total_weight));
    for(size_t i = 0; i < Pheromones.size(); ++i) {
        if(!Pheromones[i].IsActive()) {
            continue;
        }

        const argos::Real current_weight = Pheromones[i].SelectionWeight();
        if(random_weight < current_weight) {
            target_out = Pheromones[i].location;
            if(trail_out != NULL) {
                *trail_out = Pheromones[i].trail;
            }
            return true;
        }
        random_weight -= current_weight;
    }

    return false;
}

size_t RobotPheromoneMemory::Size() const {
    return Pheromones.size();
}

void RobotPheromoneMemory::EnforceCapacity() {
    if(MaxPheromones == 0 || Pheromones.size() <= MaxPheromones) {
        return;
    }

    std::sort(Pheromones.begin(),
              Pheromones.end(),
              [](const DecentralizedPheromone& left, const DecentralizedPheromone& right) {
                  if(left.IsActive() != right.IsActive()) {
                      return left.IsActive();
                  }
                  if(left.weight != right.weight) {
                      return left.weight > right.weight;
                  }
                  return left.last_updated_time > right.last_updated_time;
              });
    Pheromones.resize(MaxPheromones);
}
