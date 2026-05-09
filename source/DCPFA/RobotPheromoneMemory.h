#ifndef ROBOT_PHEROMONE_MEMORY_H
#define ROBOT_PHEROMONE_MEMORY_H

#include "DecentralizedPheromone.h"
#include <argos3/core/utility/math/rng.h>
#include <cstddef>

class RobotPheromoneMemory {
public:
    explicit RobotPheromoneMemory(size_t max_pheromones = 128);

    void Clear();
    void SetMaxSize(size_t max_pheromones);

    void AddLocalPheromone(const std::string& origin_robot_id,
                           size_t creation_tick,
                           const argos::CVector2& location,
                           const std::vector<argos::CVector2>& trail,
                           argos::Real current_time,
                           argos::Real decay_rate,
                           size_t resource_density);

    bool ReceivePheromone(const DecentralizedPheromone& incoming);
    size_t ReceivePheromones(const std::vector<DecentralizedPheromone>& incoming);
    std::vector<DecentralizedPheromone> ExportActivePheromones() const;
    void DecayAndPrune(argos::Real current_time);
    bool SelectTarget(argos::CRandom::CRNG* rng,
                      argos::CVector2& target_out,
                      std::vector<argos::CVector2>* trail_out = NULL) const;
    size_t Size() const;

private:
    void EnforceCapacity();

    size_t MaxPheromones;
    std::vector<DecentralizedPheromone> Pheromones;
};

#endif
