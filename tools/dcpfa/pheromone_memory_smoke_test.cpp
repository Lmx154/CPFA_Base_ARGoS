#include <source/DCPFA/RobotPheromoneMemory.h>

#include <argos3/core/utility/math/rng.h>
#include <cmath>
#include <iostream>
#include <string>
#include <vector>

namespace {

bool NearlyEqual(argos::Real left, argos::Real right, argos::Real epsilon = 1e-9) {
    return std::fabs(left - right) <= epsilon;
}

bool SamePoint(const argos::CVector2& left, const argos::CVector2& right) {
    return (left - right).SquareLength() <= 1e-9;
}

void Require(bool condition, const std::string& message) {
    if(!condition) {
        std::cerr << "FAIL: " << message << std::endl;
        std::exit(1);
    }
    std::cout << "PASS: " << message << std::endl;
}

} // namespace

int main() {
    RobotPheromoneMemory local_memory(4);
    const argos::CVector2 food_location(1.25, -0.75);
    std::vector<argos::CVector2> trail;
    trail.push_back(food_location);
    trail.push_back(argos::CVector2(0.0, 0.0));

    local_memory.AddLocalPheromone("robot_a",
                                   42,
                                   food_location,
                                   trail,
                                   10.0,
                                   0.5,
                                   3);
    Require(local_memory.Size() == 1, "local pheromone can be created");

    std::vector<DecentralizedPheromone> exported = local_memory.ExportActivePheromones();
    Require(exported.size() == 1, "local pheromone can be exported");
    Require(exported[0].id == DecentralizedPheromone::MakeId("robot_a", 42, food_location),
            "local pheromone ID is deterministic");

    Require(!local_memory.ReceivePheromone(exported[0]),
            "duplicate pheromone is ignored as a new entry");
    Require(local_memory.Size() == 1, "duplicate pheromone does not grow memory");

    DecentralizedPheromone fresher_duplicate = exported[0];
    fresher_duplicate.weight = 2.0;
    fresher_duplicate.last_updated_time = 12.0;
    fresher_duplicate.hop_count = 2;
    Require(!local_memory.ReceivePheromone(fresher_duplicate),
            "duplicate pheromone is merged instead of inserted");

    exported = local_memory.ExportActivePheromones();
    Require(exported.size() == 1, "merged duplicate keeps one memory entry");
    Require(NearlyEqual(exported[0].weight, 2.0), "merged duplicate updates stronger weight");
    Require(exported[0].hop_count == 2, "merged duplicate preserves fresher relay metadata");

    RobotPheromoneMemory relay_memory(4);
    Require(relay_memory.ReceivePheromone(exported[0]),
            "received pheromone is accepted by another robot");
    Require(relay_memory.Size() == 1, "receiver stores accepted pheromone");
    Require(relay_memory.ExportActivePheromones().size() == 1,
            "received pheromone can be exported for relay");

    const std::string rng_category = "dcpfa_memory_smoke_test";
    if(!argos::CRandom::ExistsCategory(rng_category)) {
        argos::CRandom::CreateCategory(rng_category, 12345);
    }
    argos::CRandom::CRNG* rng = argos::CRandom::CreateRNG(rng_category);
    argos::CVector2 selected_target;
    std::vector<argos::CVector2> selected_trail;
    Require(relay_memory.SelectTarget(rng, selected_target, &selected_trail),
            "received pheromone can be selected as a target");
    Require(SamePoint(selected_target, food_location),
            "selected target matches pheromone location");
    Require(selected_trail.size() == trail.size(), "selected target returns trail metadata");

    relay_memory.DecayAndPrune(1000.0);
    Require(relay_memory.Size() == 0, "pheromone below threshold is deleted after decay");
    Require(relay_memory.ExportActivePheromones().empty(),
            "expired pheromone is not exported");

    std::cout << "PASS: RobotPheromoneMemory Phase B smoke test complete" << std::endl;
    return 0;
}
