#include "DCPFA_qt_user_functions.h"

/*****
 * Constructor: In order for drawing functions in this class to be used by
 * ARGoS it must be registered using the RegisterUserFunction function.
 *****/
DCPFA_qt_user_functions::DCPFA_qt_user_functions() :
	loopFunctions(dynamic_cast<DCPFA_loop_functions&>(CSimulator::GetInstance().GetLoopFunctions()))
{
	RegisterUserFunction<DCPFA_qt_user_functions, CFootBotEntity>(&DCPFA_qt_user_functions::DrawOnRobot);
	RegisterUserFunction<DCPFA_qt_user_functions, CFloorEntity>(&DCPFA_qt_user_functions::DrawOnArena);
}

void DCPFA_qt_user_functions::DrawOnRobot(CFootBotEntity& entity) {
	DCPFA_controller& c = dynamic_cast<DCPFA_controller&>(entity.GetControllableEntity().GetController());

	if(c.IsHoldingFood()) {
		DrawCylinder(CVector3(0.0, 0.0, 0.3), CQuaternion(), loopFunctions.FoodRadius, 0.025, CColor::BLACK);
	}

	if(loopFunctions.DebugCommunication == 1) {
		DrawCircle(CVector3(0.0, 0.0, 0.01), CQuaternion(), loopFunctions.CommunicationRadius, CColor::BLUE);
	}

	if(loopFunctions.DrawIDs == 1) {
		/* Disable lighting, so it does not interfere with the chosen text color */
		glDisable(GL_LIGHTING);
		/* Disable face culling to be sure the text is visible from anywhere */
		glDisable(GL_CULL_FACE);
		/* Set the text color */
		CColor cColor(CColor::BLACK);
		glColor3ub(cColor.GetRed(), cColor.GetGreen(), cColor.GetBlue());

		/* The position of the text is expressed wrt the reference point of the footbot
		 * For a foot-bot, the reference point is the center of its base.
		 * See also the description in
		 * $ argos3 -q foot-bot
		 */
		
		// Disable for now
		//GetOpenGLWidget().renderText(0.0, 0.0, 0.5,             // position
		//			     entity.GetId().c_str()); // text
		
			DrawText(CVector3(0.0, 0.0, 0.3),   // position
            entity.GetId().c_str()); // text
		/* Restore face culling */
		glEnable(GL_CULL_FACE);
		/* Restore lighting */
		glEnable(GL_LIGHTING);
	}
}
 
void DCPFA_qt_user_functions::DrawOnArena(CFloorEntity& entity) {
	DrawFood();
	DrawFidelity();
	DrawPheromones();
	DrawNest();

	if(loopFunctions.DrawTargetRays == 1) DrawTargetRays();
}

/*****
 * This function is called by the DrawOnArena(...) function. If the iAnt_data
 * object is not initialized this function should not be called.
 *****/
void DCPFA_qt_user_functions::DrawNest() {
	/* 2d cartesian coordinates of the nest */
	Real x_coordinate = loopFunctions.NestPosition.GetX();
	Real y_coordinate = loopFunctions.NestPosition.GetY();

	/* required: leaving this 0.0 will draw the nest inside of the floor */
	Real elevation = loopFunctions.NestElevation;

	/* 3d cartesian coordinates of the nest */
	CVector3 nest_3d(x_coordinate, y_coordinate, elevation);

	/* Draw the nest on the arena. */
	//DrawCircle(nest_3d, CQuaternion(), loopFunctions.NestRadius, CColor::RED);
    DrawCylinder(nest_3d, CQuaternion(), loopFunctions.NestRadius, 0.008, CColor::GREEN);
}

void DCPFA_qt_user_functions::DrawFood() {

	Real x, y;

	for(size_t i = 0; i < loopFunctions.FoodList.size(); i++) {
		x = loopFunctions.FoodList[i].GetX();
		y = loopFunctions.FoodList[i].GetY();
		DrawCylinder(CVector3(x, y, 0.002), CQuaternion(), loopFunctions.FoodRadius, 0.025, loopFunctions.FoodColoringList[i]);
	}
 
	 //draw food in nests
	 for (size_t i=0; i< loopFunctions.CollectedFoodList.size(); i++)
	 { 
	        x = loopFunctions.CollectedFoodList[i].GetX();
	        y = loopFunctions.CollectedFoodList[i].GetY();
	        DrawCylinder(CVector3(x, y, 0.002), CQuaternion(), loopFunctions.FoodRadius, 0.025, CColor::BLACK);
	  } 
}

void DCPFA_qt_user_functions::DrawFidelity() {

	   Real x, y;
        for(map<string, CVector2>::iterator it= loopFunctions.FidelityList.begin(); it!=loopFunctions.FidelityList.end(); ++it) {
            x = it->second.GetX();
            y = it->second.GetY();
            DrawCylinder(CVector3(x, y, 0.0), CQuaternion(), loopFunctions.FoodRadius, 0.025, CColor::YELLOW);
        }
}

void DCPFA_qt_user_functions::DrawPheromones() {

	Real x, y, weight;
	vector<CVector2> trail;
	CColor trailColor = CColor::GREEN, pColor = CColor::GREEN;

	argos::CSpace::TMapPerType& footbots = loopFunctions.GetSpace().GetEntitiesByType("foot-bot");
	for(argos::CSpace::TMapPerType::iterator it = footbots.begin(); it != footbots.end(); it++) {
		argos::CFootBotEntity& footBot = *argos::any_cast<argos::CFootBotEntity*>(it->second);
		DCPFA_controller& controller = dynamic_cast<DCPFA_controller&>(footBot.GetControllableEntity().GetController());
		std::vector<DecentralizedPheromone> pheromones = controller.ExportActivePheromones();

	    for(size_t i = 0; i < pheromones.size(); i++) {
		       x = pheromones[i].location.GetX();
		       y = pheromones[i].location.GetY();

		       if(loopFunctions.DrawTrails == 1) {
			          trail  = pheromones[i].trail;
			          weight = pheromones[i].weight;
                

             if(weight > 0.25 && weight <= 1.0)        // [ 100.0% , 25.0% )
                 pColor = trailColor = CColor::GREEN;
             else if(weight > 0.05 && weight <= 0.25)  // [  25.0% ,  5.0% )
                 pColor = trailColor = CColor::YELLOW;
             else                                      // [   5.0% ,  0.0% ]
                 pColor = trailColor = CColor::RED;
      
             CRay3 ray;
             size_t j = 0;
      
             for(j = 1; j < trail.size(); j++) {
                 ray = CRay3(CVector3(trail[j - 1].GetX(), trail[j - 1].GetY(), 0.01),
		CVector3(trail[j].GetX(), trail[j].GetY(), 0.01));
                 
                 DrawRay(ray, trailColor, 1.0);
             }

	 DrawCylinder(CVector3(x, y, 0.0), CQuaternion(), loopFunctions.FoodRadius, 0.025, pColor);
		       } 
         else {
			          weight = pheromones[i].weight;

             if(weight > 0.25 && weight <= 1.0)        // [ 100.0% , 25.0% )
                 pColor = CColor::GREEN;
             else if(weight > 0.05 && weight <= 0.25)  // [  25.0% ,  5.0% )
                 pColor = CColor::YELLOW;
             else                                      // [   5.0% ,  0.0% ]
                 pColor = CColor::RED;
      
             DrawCylinder(CVector3(x, y, 0.0), CQuaternion(), loopFunctions.FoodRadius, 0.025, pColor);
         }
 }
	}
}

void DCPFA_qt_user_functions::DrawTargetRays() {
	//size_t tick = loopFunctions.GetSpace().GetSimulationClock();
	//size_t tock = loopFunctions.GetSimulator().GetPhysicsEngine("default").GetInverseSimulationClockTick() / 8;

	//if(tock == 0) tock = 1;

	//if(tick % tock == 0) {
		for(size_t j = 0; j < loopFunctions.TargetRayList.size(); j++) {
			DrawRay(loopFunctions.TargetRayList[j], loopFunctions.TargetRayColorList[j]);
		}
	//}
}

/*
void DCPFA_qt_user_functions::DrawTargetRays() {

	CColor c = CColor::BLUE;

	for(size_t j = 0; j < loopFunctions.TargetRayList.size(); j++) {
			DrawRay(loopFunctions.TargetRayList[j],c);
	}

	//if(loopFunctions.SimTime % (loopFunctions.TicksPerSecond * 10) == 0) {
		// comment out for DSA, uncomment for DCPFA
		loopFunctions.TargetRayList.clear();
	//}
}
*/

REGISTER_QTOPENGL_USER_FUNCTIONS(DCPFA_qt_user_functions, "DCPFA_qt_user_functions")
