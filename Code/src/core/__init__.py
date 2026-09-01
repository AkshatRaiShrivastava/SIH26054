"""
Core business logic for physics evaluation and environmental modeling.

Modules:
- environmental_model: Climate-zone dependent parameter generation
- environmental_physics: Density altitude, icing risk, fault attribution
- physics_layer: Live physics evaluation & debounced status updates

Usage:
    from src.core.environmental_model import EnvironmentalModel
    from src.core.environmental_physics import EnvironmentalPhysics
    from src.core.physics_layer import PhysicsEvaluator
"""

# Modules are available but not imported at package level to avoid circular dependencies
# Users should import directly: from src.core.physics_layer import PhysicsEvaluator

__all__ = ["environmental_model", "environmental_physics", "physics_layer"]
